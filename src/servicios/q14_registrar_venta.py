"""Q14: registrar una venta Completada con receta y stock atómicos.

    python src/servicios/q14_registrar_venta.py --id-venta V902 \
      --id-cliente C009 --id-farmaceutico F008 --medio-pago Débito \
      --item PRD014:20 --item PRD015:2

La venta, modificación de receta, Q15 y evento de sincronización se ejecutan
DENTRO de una única transacción MongoDB; Redis NO participa del commit.
"""
import argparse
import os
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from pprint import pprint
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.servicios.q15_actualizar_stock import aplicar_stock_venta
from src.servicios.reglas_stock import ReglaNegocioError, validar_items_y_agrupar

URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
BD = os.getenv("MONGO_DB", "farmared")
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
MEDIOS = {"Efectivo", "Débito", "Crédito", "Transferencia", "Obra social"}
REQUIERE_RECETA = {"Bajo receta", "Bajo receta archivada"}


def actualizar_receta(db, id_receta, id_cliente, hoy, session):
    receta = db.recetas.find_one({"_id": id_receta}, session=session)
    if not receta or receta.get("id_cliente") != id_cliente or receta.get("estado") != "Vigente":
        raise ReglaNegocioError("La receta debe existir, estar Vigente y pertenecer al cliente")
    autorizadas = receta["dispensas_autorizadas"]
    realizadas = receta["dispensas_realizadas"]
    if any(type(x) is not int for x in (autorizadas, realizadas)) or not 0 <= realizadas < autorizadas:
        raise ReglaNegocioError("La receta no tiene dispensas disponibles")
    if receta["tipo"] in ("Simple", "Archivada") and (autorizadas != 1 or realizadas != 0):
        raise ReglaNegocioError("Una receta Simple/Archivada solo admite una dispensa")
    siguiente = realizadas + 1
    completa = siguiente == autorizadas
    proxima = None if completa else datetime.combine(
        hoy + timedelta(days=30), time.min, tzinfo=timezone.utc
    )
    actualizado = db.recetas.update_one({
        "_id": id_receta,
        "id_cliente": id_cliente,
        "estado": "Vigente",
        "dispensas_realizadas": realizadas,
    }, {"$set": {
        "dispensas_realizadas": siguiente,
        "proxima_dispensa": proxima,
        "estado": "Completada" if completa else "Vigente",
    }}, session=session)
    if actualizado.modified_count != 1:
        raise ReglaNegocioError("La receta fue modificada simultáneamente; reintentar")
    return {"id_receta": id_receta, "dispensas_realizadas": siguiente,
            "estado": "Completada" if completa else "Vigente", "proxima_dispensa": proxima}


def registrar_venta(client, id_venta, id_cliente, id_farmaceutico, medio_pago,
                   items, id_receta=None, hoy=None):
    """Crea venta completada, aplica receta y stock (Q15), todo o nada.

    items: lista [{id_producto: str, cantidad: int}]; precios se toman del
    catálogo actual y se guardan como foto del precio en cada ítem.
    Devuelve un resumen del commit y los lotes consumidos.
    """
    if not all(isinstance(x, str) and x.strip() for x in
               (id_venta, id_cliente, id_farmaceutico, medio_pago)):
        raise ReglaNegocioError("Los identificadores y medio de pago son obligatorios")
    if medio_pago not in MEDIOS:
        raise ReglaNegocioError(f"Medio de pago inválido: {medio_pago}")
    cantidades = validar_items_y_agrupar(items)
    # no se hace I/O con Redis dentro de esta función transaccional.
    hoy = hoy or datetime.now(ZONA).date()
    fecha_venta = datetime.combine(hoy, time.min, tzinfo=timezone.utc)
    db = client[BD]

    def trabajo(session):
        if db.ventas.find_one({"_id": id_venta}, {"_id": 1}, session=session):
            raise ReglaNegocioError(f"El identificador {id_venta} ya existe: no se descuenta stock nuevamente")
        cliente = db.clientes.find_one({"_id": id_cliente}, session=session)
        if not cliente or cliente.get("activo") is not True:
            raise ReglaNegocioError("El cliente debe existir y estar activo")
        farm = db.farmaceuticos.find_one({"_id": id_farmaceutico}, session=session)
        if not farm or farm.get("activo") is not True:
            raise ReglaNegocioError("El farmacéutico debe existir y estar activo")
        suc = db.sucursales.find_one({"_id": farm["id_sucursal"]}, session=session)
        if not suc or suc.get("tipo") != "Farmacia" or suc.get("activo") is not True:
            raise ReglaNegocioError("La sucursal debe existir, estar activa y ser de tipo Farmacia")

        # Verifica cada producto y conserva su precio de catálogo en el momento.
        productos = {}
        necesita_receta = False
        for producto_id in cantidades:
            producto = db.productos.find_one({"_id": producto_id}, session=session)
            if not producto or producto.get("activo") is not True:
                raise ReglaNegocioError(f"Producto inexistente o inactivo: {producto_id}")
            if type(producto.get("precio_unit")) is not int or producto["precio_unit"] < 0:
                raise ReglaNegocioError(f"Precio inválido para {producto_id}")
            condicion = producto.get("condicion_venta")
            if condicion not in {"Venta libre", *REQUIERE_RECETA}:
                raise ReglaNegocioError(f"Condición de venta no reconocida en {producto_id}")
            if condicion in REQUIERE_RECETA:
                necesita_receta = True
            productos[producto_id] = producto

        if necesita_receta and not id_receta:
            raise ReglaNegocioError("La venta contiene productos Bajo receta y requiere id_receta")
        if id_receta and not necesita_receta:
            raise ReglaNegocioError("La venta solo contiene productos libres: no debe afectar una receta")

        detalles = []
        for n, item in enumerate(items, start=1):
            producto = productos[item["id_producto"]]
            detalles.append({
                "id_detalle": f"{id_venta}-D{n:02d}",
                "id_producto": item["id_producto"],
                "cantidad": item["cantidad"],
                "precio_unit": producto["precio_unit"],
            })
        total = sum(item["cantidad"] * item["precio_unit"] for item in detalles)
        venta = {
            "_id": id_venta, "id_venta": id_venta,
            "id_cliente": id_cliente, "id_farmaceutico": id_farmaceutico,
            "id_sucursal": farm["id_sucursal"], "id_receta": id_receta,
            "fecha": fecha_venta, "tipo": "Con receta" if necesita_receta else "Venta libre",
            "medio_pago": medio_pago, "total": total,
            "estado": "Completada", "stock_aplicado": False,
            "redis_sync": "pendiente", "items": detalles,
        }
        db.ventas.insert_one(venta, session=session)
        receta_resultado = (actualizar_receta(db, id_receta, id_cliente, hoy, session)
                            if necesita_receta else None)
        stock_resultado = aplicar_stock_venta(
            db, id_venta, farm["id_sucursal"], hoy, session
        )
        # La marca redis_sync viaja en el mismo documento de venta.
        # No necesitamos crear una colección adicional de eventos.
        return {
            "id_venta": id_venta, "id_cliente": id_cliente,
            "id_farmaceutico": id_farmaceutico, "id_sucursal": farm["id_sucursal"],
            "total": total, "tipo": venta["tipo"], "estado": "Completada",
            "receta": receta_resultado, "lotes_consumidos": stock_resultado["lotes_consumidos"],
        }

    with client.start_session() as session:
        try:
            return session.with_transaction(
                trabajo, read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
            )
        except DuplicateKeyError as exc:
            raise ReglaNegocioError(f"ID de venta/evento duplicado: {id_venta}") from exc


def parsear_item(s):
    try:
        id_producto, cantidad_txt = s.rsplit(":", 1)
        cantidad = int(cantidad_txt)
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError("Se espera PRD014:2") from exc
    if not id_producto or cantidad <= 0:
        raise argparse.ArgumentTypeError("Producto y cantidad positiva requeridos")
    return {"id_producto": id_producto, "cantidad": cantidad}


def main():
    ap = argparse.ArgumentParser(description="Q14: registrar venta Completada con FEFO integrado")
    ap.add_argument("--id-venta", required=True)
    ap.add_argument("--id-cliente", required=True)
    ap.add_argument("--id-farmaceutico", required=True)
    ap.add_argument("--medio-pago", required=True, choices=sorted(MEDIOS))
    ap.add_argument("--id-receta", default=None)
    ap.add_argument("--item", action="append", type=parsear_item, required=True,
                    help="Repetible, por ejemplo --item PRD014:2")
    ap.add_argument("--sin-sync", action="store_true", help="Solo para pruebas, deja evento pendiente")
    args = ap.parse_args()

    with MongoClient(URI, serverSelectionTimeoutMS=6000) as client:
        try:
            resultado = registrar_venta(
                client, args.id_venta, args.id_cliente, args.id_farmaceutico,
                args.medio_pago, args.item, args.id_receta,
            )
        except ReglaNegocioError as exc:
            ap.error(str(exc))
        print("OK Q14 + Q15: transacción MongoDB confirmada")
        pprint(resultado)

    if not args.sin_sync:
        try:
            from scripts.sincronizar_redis import sincronizar_pendientes
            n = sincronizar_pendientes()
            print(f"OK: Redis sincronizado, eventos atendidos: {n}")
        except Exception as exc:
            # Un fallo de Redis NO revierte una venta ya confirmada por MongoDB.
            print(f"AVISO: venta confirmada, Redis pendiente de sincronizar: {exc}")
            print("Reintentar: python scripts/sincronizar_redis.py")
    else:
        print("Redis no sincronizado por --sin-sync; hay un evento pendiente en MongoDB")


if __name__ == "__main__":
    main()
