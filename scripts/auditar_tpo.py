"""Auditoría de solo lectura de FarmaRed (MongoDB + Redis).

Comprueba datasets, integridad básica, índices y proyecciones Q04/Q05/Q07/Q08/Q11.
No crea, actualiza ni elimina documentos o claves. Ejecutar sin escrituras concurrentes.

    python scripts/auditar_tpo.py
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from redis import Redis

RAIZ = Path(__file__).resolve().parents[1]
MONGO_URI = os.getenv(
    "MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true"
)
MONGO_DB = os.getenv("MONGO_DB", "farmared")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
ENTIDADES = {
    "clientes": "id_cliente",
    "sucursales": "id_sucursal",
    "farmaceuticos": "id_farmaceutico",
    "proveedores": "id_proveedor",
    "productos": "id_producto",
    "stock_lotes": "id_lote",
    "recetas": "id_receta",
    "ventas": "id_venta",
    "detalle_ventas": "id_detalle",  # ítems embebidos, no colección
}


def cargar_ids(tipo: str, entidad: str, campo_pk: str) -> set[str]:
    ruta = RAIZ / "data" / tipo / f"{entidad}.csv"
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    ids = [fila[campo_pk].strip() for fila in filas]
    assert ids and all(ids) and len(set(ids)) == len(ids), (
        f"CSV inválido: {ruta} (identificadores vacíos o duplicados)"
    )
    if tipo == "adicionales":
        assert len(filas) >= 10, f"Faltan 10 registros adicionales en {entidad}"
    return set(ids)


def fecha_utc(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def mes_siguiente(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def auditar() -> int:
    fallos = []
    avisos = []

    def comprobar(etiqueta: str, ok: bool, detalle: str = "") -> None:
        prefijo = "OK" if ok else "ERROR"
        print(f"{prefijo} {etiqueta}" + (f": {detalle}" if detalle else ""))
        if not ok:
            fallos.append(etiqueta)

    # A. Fuentes CSV: sin escribir en la BD.
    esperados = {}
    for entidad, pk in ENTIDADES.items():
        try:
            originales = cargar_ids("originales", entidad, pk)
            adicionales = cargar_ids("adicionales", entidad, pk)
            comprobar(f"CSV {entidad}", not (originales & adicionales),
                      f"{len(originales)} originales + {len(adicionales)} adicionales")
            esperados[entidad] = originales | adicionales
        except Exception as exc:
            comprobar(f"CSV {entidad}", False, str(exc))

    with MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000) as mongo, Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=5
    ) as redis:
        mongo.admin.command("ping")
        redis.ping()
        db = mongo[MONGO_DB]
        colecciones = set(db.list_collection_names())
        comprobar("MongoDB: ocho colecciones", set(ENTIDADES) - {"detalle_ventas"} <= colecciones)
        comprobar("MongoDB: detalle embebido", "detalle_ventas" not in colecciones)
        for entidad in ENTIDADES:
            if entidad == "detalle_ventas" or entidad not in esperados:
                continue
            ids_bd = {str(doc["_id"]) for doc in db[entidad].find({}, {"_id": 1})}
            faltantes = esperados[entidad] - ids_bd
            comprobar(f"MongoDB: registros {entidad}", not faltantes,
                      f"{len(ids_bd)} actuales; faltan {len(faltantes)} de los CSV")
        for indice, campo, coleccion in [("DNI único", "dni", "clientes"),
                                          ("matrícula única", "matricula", "farmaceuticos")]:
            existe = any(
                datos.get("unique") and datos.get("key") == [(campo, 1)]
                for datos in db[coleccion].index_information().values()
            )
            comprobar(f"Índice {indice}", existe)
        pendientes = db.ventas.count_documents({"redis_sync": "pendiente"})
        if pendientes:
            avisos.append(
                f"Hay {pendientes} ventas con Redis pendiente; ejecutar 'python scripts/sincronizar_redis.py'"
            )

        # B. Q04: todos los estados de recetas.
        conteos_mongo = Counter(
            rec["id_cliente"] for rec in db.recetas.find({}, {"id_cliente": 1})
        )
        conteos_redis = {
            k: int(v) for k, v in redis.hgetall("farmared:recetas:conteo_por_cliente").items()
        }
        comprobar("Q04: conteos recetas Mongo = Redis", dict(conteos_mongo) == conteos_redis)

        # C. Q05: ventana dinámica de 60 días, incluidas pendientes, no anuladas.
        hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
        desde = fecha_utc(hoy - timedelta(days=59))
        hasta = fecha_utc(hoy + timedelta(days=1))
        farm_ids = [str(doc["_id"]) for doc in db.farmaceuticos.find(
            {"activo": True}, {"_id": 1}
        )]
        mongo_60 = Counter(
            str(doc["id_farmaceutico"]) for doc in db.ventas.find(
                {"estado": {"$ne": "Anulada"}, "fecha": {"$gte": desde, "$lt": hasta}},
                {"id_farmaceutico": 1}
            )
        )
        errores_05 = []
        for fid in farm_ids:
            n = redis.zcount(f"farmared:ventas:farmaceutico:{fid}",
                             int(desde.timestamp()), f"({int(hasta.timestamp())}")
            if n != mongo_60[fid]:
                errores_05.append((fid, mongo_60[fid], n))
        comprobar("Q05: ventana 60 días Mongo = Redis", not errores_05,
                  f"{len(farm_ids)} activos; diferencias={errores_05[:5]}")

        # D. Q07: unidades de ítems en ventas completadas.
        totales_mongo = defaultdict(int)
        for venta in db.ventas.find({"estado": "Completada"}, {"items": 1}):
            for item in venta.get("items", []):
                totales_mongo[str(item["id_producto"])] += int(item["cantidad"])
        totales_redis = {
            producto: int(score) for producto, score in redis.zrange(
                "farmared:ranking:productos:unidades", 0, -1, withscores=True
            )
        }
        comprobar("Q07: unidades vendidas Mongo = Redis", dict(totales_mongo) == totales_redis,
                  f"{len(totales_mongo)} productos")

        # E. Q08: índice de unidades refleja el stock real, incluidos ceros.
        stock_mongo = {
            str(lote["_id"]): int(lote["unidades"])
            for lote in db.stock_lotes.find({}, {"_id": 1, "unidades": 1})
        }
        stock_redis = {
            lote: int(score) for lote, score in redis.zrange(
                "farmared:stock:por_unidades", 0, -1, withscores=True
            )
        }
        comprobar("Q08: stock por lote Mongo = Redis", stock_mongo == stock_redis,
                  f"{len(stock_mongo)} lotes")

        # F. Q11: mes actual; incluir ceros para todos los farmacéuticos.
        desde_mes = fecha_utc(date(hoy.year, hoy.month, 1))
        hasta_mes = fecha_utc(mes_siguiente(hoy))
        totales_farm = defaultdict(int)
        for venta in db.ventas.find(
            {"estado": "Completada", "fecha": {"$gte": desde_mes, "$lt": hasta_mes}},
            {"id_farmaceutico": 1, "total": 1}
        ):
            totales_farm[str(venta["id_farmaceutico"])] += int(venta["total"])
        ids_farm = {str(x["_id"]) for x in db.farmaceuticos.find({}, {"_id": 1})}
        esperado_11 = {fid: totales_farm[fid] for fid in ids_farm}
        mes = hoy.strftime("%Y-%m")
        redis_11 = {fid: int(n) for fid, n in redis.hgetall(
            f"farmared:ingresos:farmaceutico:{mes}").items()}
        comprobar("Q11: ingresos mensuales Mongo = Redis", esperado_11 == redis_11,
                  f"{mes}, total ${sum(esperado_11.values()):,}")

    for aviso in avisos:
        print("AVISO:", aviso)
    if fallos:
        print(f"\nAuditoría: {len(fallos)} comprobaciones fallaron. No se modificó ningún dato.")
        return 1
    print("\nAuditoría de solo lectura completada: comprobaciones correctas.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(auditar())
    except Exception as error:
        print(f"ERROR de ejecución: {error}", file=sys.stderr)
        sys.exit(2)
