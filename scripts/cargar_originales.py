"""Carga idempotente de los CSV originales de FarmaRed en 8 colecciones MongoDB.

La cabecera y los items de las ventas se guardan juntos; no se hace doble
consumo de stock histórico. Este script no escribe nada en Redis.
"""
import csv
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient, UpdateOne, ASCENDING

RUTA = Path(__file__).resolve().parents[1] / "data" / "originales"
URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
BD = os.getenv("MONGO_DB", "farmared")
PK = {
    "clientes": "id_cliente", "sucursales": "id_sucursal",
    "farmaceuticos": "id_farmaceutico", "proveedores": "id_proveedor",
    "productos": "id_producto", "stock_lotes": "id_lote",
    "recetas": "id_receta", "ventas": "id_venta",
    "detalle_ventas": "id_detalle",
}
ENTEROS = {"precio_unit", "unidades", "dispensas_autorizadas", "dispensas_realizadas", "total", "cantidad"}
FECHAS = {"vencimiento", "fecha_emision", "proxima_dispensa", "fecha"}


def convertir(k, v):
    v = v.strip()
    if v == "":
        return None
    if k == "activo":
        if v not in {"True", "False"}:
            raise ValueError(f"Booleano desconocido: {k}={v}")
        return v == "True"
    if k in ENTEROS:
        return int(v)
    if k in FECHAS:
        return datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return v


def leer(n):
    archivo = RUTA / f"{n}.csv"
    with archivo.open("r", encoding="utf-8-sig", newline="") as f:
        datos = [{k: convertir(k, v) for k, v in r.items()} for r in csv.DictReader(f)]
    ids = [d[PK[n]] for d in datos]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError(f"IDs faltantes o repetidos en {n}")
    return datos


def comprobar_referencias(d):
    refs = {
        "farmaceuticos": [("id_sucursal", "sucursales")],
        "productos": [("id_proveedor", "proveedores")],
        "stock_lotes": [("id_producto", "productos"), ("id_sucursal", "sucursales")],
        "recetas": [("id_cliente", "clientes")],
        "ventas": [("id_cliente", "clientes"), ("id_farmaceutico", "farmaceuticos"), ("id_receta", "recetas")],
        "detalle_ventas": [("id_venta", "ventas"), ("id_producto", "productos")],
    }
    conjuntos = {n: {fila[PK[n]] for fila in filas} for n, filas in d.items()}
    for n, reglas in refs.items():
        for fila in d[n]:
            for campo, destino in reglas:
                v = fila[campo]
                if v is not None and v not in conjuntos[destino]:
                    raise ValueError(f"Referencia inexistente: {n}.{campo}={v} en {destino}")


def preparar_ventas(d):
    items_por_venta = defaultdict(list)
    for fila in d["detalle_ventas"]:
        items_por_venta[fila["id_venta"]].append(
            {k: v for k, v in fila.items() if k != "id_venta"}
        )
    resultado = []
    for venta in d["ventas"]:
        items = items_por_venta.pop(venta["id_venta"], [])
        if not items or any(i["cantidad"] <= 0 for i in items):
            raise ValueError(f"Detalle inválido de venta {venta['id_venta']}")
        total = sum(i["cantidad"] * i["precio_unit"] for i in items)
        if total != venta["total"]:
            raise ValueError(f"Total de {venta['id_venta']} inconsistente: {total} vs {venta['total']}")
        resultado.append({
            **venta,
            "items": items,
            # Supuesto inicial: el inventario CSV es un saldo de partida.
            # Nunca volver a descontar las ventas históricas completas.
            "stock_aplicado": venta["estado"] == "Completada",
        })
    if items_por_venta:
        raise ValueError("Detalles de ventas sin cabecera")
    return resultado


def main():
    datos = {nombre: leer(nombre) for nombre in PK}
    comprobar_referencias(datos)
    datos["ventas"] = preparar_ventas(datos)
    with MongoClient(URI, serverSelectionTimeoutMS=5000) as cliente:
        cliente.admin.command("ping")
        db = cliente[BD]
        for nombre, filas in datos.items():
            if nombre == "detalle_ventas":
                continue
            docs = [{"_id": fila[PK[nombre]], **fila} for fila in filas]
            operaciones = [
                UpdateOne({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
                for doc in docs
            ]
            res = db[nombre].bulk_write(operaciones, ordered=True)
            print(f"{nombre}: {len(docs)} CSV; {res.upserted_count} nuevos; "
                  f"{db[nombre].count_documents({})} en MongoDB")

        db.clientes.create_index("dni", unique=True)
        db.farmaceuticos.create_index("matricula", unique=True)
        db.ventas.create_index([("id_cliente", ASCENDING), ("fecha", ASCENDING)])
        db.ventas.create_index([("id_farmaceutico", ASCENDING), ("fecha", ASCENDING)])
        db.ventas.create_index([("estado", ASCENDING), ("fecha", ASCENDING)])
        db.stock_lotes.create_index([
            ("id_sucursal", ASCENDING), ("id_producto", ASCENDING),
            ("vencimiento", ASCENDING)])
        db.stock_lotes.create_index("unidades")
        db.recetas.create_index([("estado", ASCENDING), ("proxima_dispensa", ASCENDING)])
    print("Carga original finalizada. Redis aún no se carga en esta etapa.")


if __name__ == "__main__":
    main()
