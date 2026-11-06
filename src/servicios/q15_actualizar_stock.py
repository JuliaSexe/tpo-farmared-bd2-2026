"""Q15: descuenta stock por FEFO (MongoDB, dentro de una transacción).

Función central: aplicar_stock_venta(db, id_venta, id_sucursal, hoy, session)
  - Llama desde Q14, en la MISMA transacción que venta y receta.
  - Puede invocarse desde ejecutar_q15() para ventas COMPLETADAS previamente
    registradas pero con stock_aplicado=False, por ejemplo una carga de prueba.
  - No vuelve a descontar si stock_aplicado=True.

Los lotes vencidos (vencimiento < hoy) no se usan. 'Hoy' se calcula con
America/Argentina/Buenos_Aires; las fechas BSON de los CSV son 00:00 UTC.
"""
import argparse
import os
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from pprint import pprint
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.servicios.reglas_stock import ReglaNegocioError, planificar_consumo_fefo

URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
BD = os.getenv("MONGO_DB", "farmared")
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def limite_vencimiento(hoy):
    return datetime.combine(hoy, time.min, tzinfo=timezone.utc)


def aplicar_stock_venta(db, id_venta, id_sucursal, hoy, session):
    """Consume los ítems de una venta, con todas las escrituras en `session`.

    Devuelve {ya_aplicado, lotes_consumidos}. Rechaza stock insuficiente SIN
    efectos persistidos cuando la transacción envolvente es abortada.
    """
    venta = db.ventas.find_one({"_id": id_venta}, session=session)
    if not venta:
        raise ReglaNegocioError(f"La venta {id_venta} no existe")
    if venta.get("estado") != "Completada":
        raise ReglaNegocioError("Q15 solo procesa ventas Completada")
    if venta.get("stock_aplicado") is True:
        return {"ya_aplicado": True, "lotes_consumidos": venta.get("lotes_consumidos", [])}
    if venta.get("stock_aplicado") is not False:
        raise ReglaNegocioError("Venta sin marca de stock_aplicado: revisar migración")
    if venta.get("id_sucursal") and venta["id_sucursal"] != id_sucursal:
        raise ReglaNegocioError("La sucursal de la venta no coincide con la indicada")

    # Los ítems pueden repetir producto; la planificación los agrupa.
    items = venta["items"]
    cantidades = {x["id_producto"] for x in items}
    corte = limite_vencimiento(hoy)
    lotes_por_producto = {}
    for producto in cantidades:
        lotes_por_producto[producto] = list(db.stock_lotes.find({
            "id_producto": producto,
            "id_sucursal": id_sucursal,
            "vencimiento": {"$gte": corte},
            "unidades": {"$gt": 0},
        }, session=session).sort([("vencimiento", 1), ("_id", 1)]))

    # Plan completo primero, descuento condicionado después.
    plan = planificar_consumo_fefo(items, lotes_por_producto)
    for paso in plan:
        actualizado = db.stock_lotes.update_one({
            "_id": paso["id_lote"],
            "id_sucursal": id_sucursal,
            "id_producto": paso["id_producto"],
            "vencimiento": {"$gte": corte},
            "unidades": {"$gte": paso["cantidad"]},
        }, {"$inc": {"unidades": -paso["cantidad"]}}, session=session)
        if actualizado.modified_count != 1:
            # Puede haber concurrencia: el callback de with_transaction reintenta
            # ante errores transitorios, pero no debe realizar cambios parciales.
            raise ReglaNegocioError(f"Cambio de stock concurrente en {paso['id_lote']}; reintentar")

    marcado = db.ventas.update_one({
        "_id": id_venta, "estado": "Completada", "stock_aplicado": False
    }, {"$set": {"stock_aplicado": True, "lotes_consumidos": plan}}, session=session)
    if marcado.modified_count != 1:
        raise ReglaNegocioError("La venta ya fue procesada por otro intento")
    return {"ya_aplicado": False, "lotes_consumidos": plan}


def ejecutar_q15(client, id_venta, hoy=None):
    """Entrada autónoma para procesar una venta Completada todavía no aplicada.

    Q14 la invoca ANTES de confirmar. Esta entrada sirve para casos migrados o
    pruebas controladas, y NO puede crear ventas nuevas ni alterar recetas.
    """
    db = client[BD]
    hoy = hoy or datetime.now(ZONA).date()

    def trabajo(session):
        venta = db.ventas.find_one({"_id": id_venta}, session=session)
        if not venta:
            raise ReglaNegocioError(f"Venta inexistente: {id_venta}")
        farm = db.farmaceuticos.find_one({"_id": venta["id_farmaceutico"]}, session=session)
        if not farm:
            raise ReglaNegocioError("La venta refiere a un farmacéutico inexistente")
        sucursal = db.sucursales.find_one({"_id": farm["id_sucursal"]}, session=session)
        if not sucursal or sucursal.get("tipo") != "Farmacia":
            raise ReglaNegocioError("La venta no pertenece a una Farmacia")
        resultado = aplicar_stock_venta(db, id_venta, farm["id_sucursal"], hoy, session)
        if not resultado["ya_aplicado"]:
            db.ventas.update_one({"_id": id_venta},
                {"$set": {"redis_sync": "pendiente"}}, session=session)
        return resultado

    with client.start_session() as session:
        return session.with_transaction(
            trabajo, read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
        )


def main():
    ap = argparse.ArgumentParser(description="Q15: procesar stock de una venta registrada")
    ap.add_argument("id_venta", help="Identificador de venta Completada")
    args = ap.parse_args()
    with MongoClient(URI, serverSelectionTimeoutMS=6000) as client:
        try:
            resultado = ejecutar_q15(client, args.id_venta)
        except ReglaNegocioError as exc:
            ap.error(str(exc))
        pprint(resultado)
        if not resultado["ya_aplicado"]:
            print("Se creó un evento pendiente para actualizar Redis; ejecutar scripts/sincronizar_redis.py")


if __name__ == "__main__":
    main()
