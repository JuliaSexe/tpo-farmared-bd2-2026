"""Reconstruye las proyecciones Redis a partir de MongoDB (FarmaRed).

Usar dentro del contenedor de Codespaces:
    python scripts/construir_redis.py

MongoDB es la fuente de verdad. Este script SOLO LEE MongoDB y reemplaza
las claves Redis que administra: nunca descuenta stock ni registra ventas.
Es idempotente: al ejecutarlo dos veces no duplica cantidades ni ingresos.

IMPORTANTE: es una reconstruccion completa MANUAL. Hasta implementar la
sincronizacion posterior a cada transaccion, volver a ejecutar el script
para actualizar Redis si se modifican ventas o lotes en MongoDB. Para evitar
lecturas mezcladas, no ejecutar durante escrituras concurrentes sobre esas
colecciones. La sincronizacion automatica se desarrollara en otra etapa.
"""

import os
from collections import defaultdict
from datetime import date, datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from redis import Redis

URI = os.getenv(
    "MONGO_URI",
    "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true",
)
BD = os.getenv("MONGO_DB", "farmared")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Claves mantenidas exclusivamente por este script.
STOCK_UNIDADES = "farmared:stock:por_unidades"
STOCK_VENCIMIENTOS = "farmared:stock:por_vencimiento"
RANKING_PRODUCTOS = "farmared:ranking:productos:unidades"
PREFIJO_INGRESOS = "farmared:ingresos:farmaceutico:"


def dia_utc_a_score(valor):
    """Fecha de calendario importada como BSON Date -> inicio del dia UTC.

    Las fechas de los CSV no son instantes horarios de negocio: se guardaron
    a las 00:00 UTC. No convertir a hora de Argentina (cambiaria el dia).
    """
    if not isinstance(valor, datetime):
        raise ValueError(f"Vencimiento no es datetime: {valor!r}")
    return int(datetime.combine(valor.date(), time.min, tzinfo=timezone.utc).timestamp())


def calcular_proyecciones(lotes, ventas, farmaceuticos, mes_actual):
    """Calcula estructuras Redis, sin conectarse ni modificar ninguna base."""
    unidades_por_lote = {}
    vencimientos_por_lote = {}
    for lote in lotes:
        id_lote = str(lote["_id"])
        unidades = lote["unidades"]
        if not isinstance(unidades, int) or isinstance(unidades, bool) or unidades < 0:
            raise ValueError(f"Unidades invalidas en lote {id_lote}: {unidades!r}")
        unidades_por_lote[id_lote] = unidades
        # Solo hay alerta de vencimiento para lotes que conservan unidades.
        if unidades > 0:
            vencimientos_por_lote[id_lote] = dia_utc_a_score(lote["vencimiento"])

    unidades_por_producto = defaultdict(int)
    ingresos_por_mes = defaultdict(lambda: defaultdict(int))
    for venta in ventas:
        if venta["estado"] != "Completada":
            continue  # Pendiente y Anulada no aportan ingresos ni unidades.
        fecha = venta["fecha"]
        if not isinstance(fecha, datetime):
            raise ValueError(f"Fecha invalida en venta {venta['_id']}")
        mes = fecha.strftime("%Y-%m")  # Fecha original del CSV, guardada como UTC.
        farmaceutico = str(venta["id_farmaceutico"])
        total = venta["total"]
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError(f"Total invalido en venta {venta['_id']}")
        ingresos_por_mes[mes][farmaceutico] += total

        for item in venta["items"]:
            cantidad = item["cantidad"]
            if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0:
                raise ValueError(f"Cantidad invalida en venta {venta['_id']}")
            unidades_por_producto[str(item["id_producto"])] += cantidad

    # En el mes actual se incluyen todos los farmaceuticos con 0 cuando no
    # tienen ventas. Eso permite mostrar una vista completa para q11.
    for f in farmaceuticos:
        ingresos_por_mes[mes_actual].setdefault(str(f["_id"]), 0)

    return (
        unidades_por_lote,
        vencimientos_por_lote,
        dict(unidades_por_producto),
        {mes: dict(montos) for mes, montos in ingresos_por_mes.items()},
    )


def escribir_redis(redis, proyecciones):
    """Reemplaza las claves propias en un solo MULTI/EXEC de Redis.

    La transaccion Redis no incluye MongoDB: protege solo la publicacion de
    la reconstruccion. Todos los datos se validan ANTES de empezar a escribir.
    """
    unidades, vencimientos, ranking, ingresos = proyecciones
    antiguas = list(redis.scan_iter(match=f"{PREFIJO_INGRESOS}*"))
    claves = [STOCK_UNIDADES, STOCK_VENCIMIENTOS, RANKING_PRODUCTOS, *antiguas]

    with redis.pipeline(transaction=True) as pipe:
        pipe.delete(*claves)
        if unidades:
            pipe.zadd(STOCK_UNIDADES, unidades)
        if vencimientos:
            pipe.zadd(STOCK_VENCIMIENTOS, vencimientos)
        if ranking:
            pipe.zadd(RANKING_PRODUCTOS, ranking)
        for mes, montos in sorted(ingresos.items()):
            if montos:
                pipe.hset(f"{PREFIJO_INGRESOS}{mes}", mapping=montos)
        pipe.execute()


def main():
    mes_actual = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%Y-%m")

    with MongoClient(URI, serverSelectionTimeoutMS=5000) as mongo:
        mongo.admin.command("ping")
        db = mongo[BD]
        lotes = list(db.stock_lotes.find({}, {"_id": 1, "unidades": 1, "vencimiento": 1}))
        ventas = list(db.ventas.find({}, {
            "_id": 1, "estado": 1, "fecha": 1, "total": 1,
            "id_farmaceutico": 1, "items": 1,
        }))
        farmaceuticos = list(db.farmaceuticos.find({}, {"_id": 1}))

    if not lotes or not ventas or not farmaceuticos:
        raise RuntimeError("Faltan datos en MongoDB. Ejecutar antes cargar_originales.py")
    proyecciones = calcular_proyecciones(lotes, ventas, farmaceuticos, mes_actual)

    with Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True) as redis:
        redis.ping()
        escribir_redis(redis, proyecciones)
        print("OK: proyecciones Redis reconstruidas desde MongoDB.")
        print(f"  Stock: {redis.zcard(STOCK_UNIDADES)} lotes indexados por unidades")
        print(f"  Vencimientos: {redis.zcard(STOCK_VENCIMIENTOS)} lotes con stock")
        print(f"  Ranking: {redis.zcard(RANKING_PRODUCTOS)} productos vendidos")
        print(f"  Ingresos: {len(proyecciones[3])} meses")
        print("  Lotes con menos de 50 unidades:",
              redis.zrangebyscore(STOCK_UNIDADES, "-inf", "(50", withscores=True))
        print("  Top 5 productos vendidos:",
              redis.zrevrange(RANKING_PRODUCTOS, 0, 4, withscores=True))
        ingresos_mes = redis.hgetall(f"{PREFIJO_INGRESOS}{mes_actual}")
        print(f"  Ingresos de {mes_actual} (ARS):", ingresos_mes)
        print("IMPORTANTE: Redis NO descuento stock ni modifico MongoDB.")


if __name__ == "__main__":
    main()
