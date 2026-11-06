"""
Prueba de concurrencia Q14 + Q15 sobre una base MongoDB AISLADA.

No usa ni modifica la base farmared ni Redis.
Crea una base temporal, ejecuta dos escenarios y la elimina al terminar.

Desde la raíz del repositorio:
    python scripts/probar_concurrencia.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.servicios import q14_registrar_venta as modulo_venta
from src.servicios.reglas_stock import ReglaNegocioError


URI = os.getenv(
    "MONGO_URI",
    "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true",
)
BASE_REAL = os.getenv("MONGO_DB", "farmared")
BASE_TEMPORAL = "farmared_concurrencia_" + uuid4().hex[:12]

CLIENTE = "C-TEST"
FARMACEUTICO = "F-TEST"
SUCURSAL = "S-TEST"
PRODUCTO = "PRD-TEST"
LOTE = "L-TEST"


def cargar_fixtures(db):
    db.clientes.insert_one({
        "_id": CLIENTE, "id_cliente": CLIENTE, "activo": True,
    })
    db.sucursales.insert_one({
        "_id": SUCURSAL, "id_sucursal": SUCURSAL,
        "tipo": "Farmacia", "activo": True,
    })
    db.farmaceuticos.insert_one({
        "_id": FARMACEUTICO, "id_farmaceutico": FARMACEUTICO,
        "id_sucursal": SUCURSAL, "activo": True,
    })
    db.productos.insert_one({
        "_id": PRODUCTO, "id_producto": PRODUCTO,
        "activo": True, "precio_unit": 100,
        "condicion_venta": "Venta libre",
    })
    db.stock_lotes.insert_one({
        "_id": LOTE, "id_lote": LOTE,
        "id_sucursal": SUCURSAL, "id_producto": PRODUCTO,
        "unidades": 10,
        "vencimiento": datetime.now(timezone.utc) + timedelta(days=365),
    })


def intentar_venta(client, id_venta, cantidad, barrera):
    barrera.wait(timeout=15)
    try:
        resultado = modulo_venta.registrar_venta(
            client=client,
            id_venta=id_venta,
            id_cliente=CLIENTE,
            id_farmaceutico=FARMACEUTICO,
            medio_pago="Efectivo",
            items=[{"id_producto": PRODUCTO, "cantidad": cantidad}],
        )
        return ("confirmada", resultado["id_venta"])
    except ReglaNegocioError as exc:
        return ("rechazada", str(exc))
    except Exception as exc:
        return ("error_inesperado", f"{type(exc).__name__}: {exc}")


def ejecutar_simultaneas(client, ventas):
    barrera = Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(intentar_venta, client, id_venta, unidades, barrera)
            for id_venta, unidades in ventas
        ]
        barrera.wait(timeout=15)
        return [future.result(timeout=60) for future in futures]


def comprobar(db, resultados, stock_esperado, ventas_esperadas):
    stock = db.stock_lotes.find_one({"_id": LOTE})["unidades"]
    ventas = list(db.ventas.find(
        {}, {"_id": 1, "stock_aplicado": 1, "lotes_consumidos": 1}
    ))
    confirmadas = [r for r in resultados if r[0] == "confirmada"]
    rechazadas = [r for r in resultados if r[0] == "rechazada"]

    print("   Resultados:", resultados)
    print("   Ventas persistidas:", [x["_id"] for x in ventas])
    print("   Stock final:", stock)

    assert len(confirmadas) == ventas_esperadas, "Cantidad de confirmaciones incorrecta"
    assert len(rechazadas) == len(resultados) - ventas_esperadas, "Rechazos inesperados"
    assert len(ventas) == ventas_esperadas, "Se persistieron ventas de más o de menos"
    assert stock == stock_esperado, f"Stock esperado {stock_esperado}, actual {stock}"
    assert stock >= 0, "Stock negativo"
    assert all(v.get("stock_aplicado") is True for v in ventas), "Hay ventas sin aplicar"
    print("   OK: transacciones, stock e idempotencia coherentes.")


def main():
    if BASE_TEMPORAL == BASE_REAL or not BASE_TEMPORAL.startswith("farmared_concurrencia_"):
        raise RuntimeError("Nombre temporal inseguro; prueba cancelada")

    # Modifica la referencia del módulo SOLO en este proceso de prueba.
    # No altera archivos ni las variables del Codespace.
    modulo_venta.BD = BASE_TEMPORAL

    print("Base de prueba aislada:", BASE_TEMPORAL)
    print("Base real preservada:", BASE_REAL)
    print("Redis: no se usa ni se modifica en esta prueba")

    with MongoClient(URI, serverSelectionTimeoutMS=6000) as client:
        db = client[BASE_TEMPORAL]
        # No se elimina una base existente: el nombre aleatorio debe estar libre.
        if db.list_collection_names():
            raise RuntimeError("La base temporal ya existía. No se modificó.")
        try:
            cargar_fixtures(db)

            print("\nPRUEBA A: dos ventas distintas de 7 unidades, stock total 10")
            resultados = ejecutar_simultaneas(
                client, [("V-CONC-A", 7), ("V-CONC-B", 7)]
            )
            comprobar(db, resultados, stock_esperado=3, ventas_esperadas=1)

            # Reinicia únicamente la base temporal, para el segundo escenario.
            db.ventas.delete_many({})
            db.stock_lotes.update_one(
                {"_id": LOTE}, {"$set": {"unidades": 10}}
            )

            print("\nPRUEBA B: dos intentos con el MISMO ID, 3 unidades cada uno")
            resultados = ejecutar_simultaneas(
                client, [("V-CONC-IGUAL", 3), ("V-CONC-IGUAL", 3)]
            )
            comprobar(db, resultados, stock_esperado=7, ventas_esperadas=1)
            print("\nOK: ambas pruebas de concurrencia pasaron.")
            return 0
        finally:
            # Solo borra esta base temporal creada para la prueba.
            client.drop_database(BASE_TEMPORAL)
            print("\nBase temporal eliminada. Los datos reales permanecen intactos.")


if __name__ == "__main__":
    raise SystemExit(main())
