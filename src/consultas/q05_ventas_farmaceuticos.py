"""Q05: farmacéuticos activos y ventas no anuladas en últimos 60 días.

MongoDB: lista completa de farmacéuticos activos. Redis: ZCOUNT sobre un
Sorted Set por farmacéutico con todas las ventas no anuladas indexadas.
La fecha es un día de calendario guardado como medianoche UTC en el CSV.
"""
import os
from datetime import datetime, timedelta, time, timezone
from pprint import pprint
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from redis import Redis

PREFIJO = "farmared:ventas:farmaceutico:"
MARCA = "farmared:meta:reconstruccion"


def q05_ventas_farmaceuticos(db, redis):
    if not redis.exists(MARCA):
        raise RuntimeError("Índice Q05 no construido. Ejecutar python scripts/construir_redis.py")

    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    # Últimos 60 días calendario, incluyendo hoy. Fechas originales en UTC 00:00.
    inicio = int(datetime.combine(hoy - timedelta(days=59), time.min, timezone.utc).timestamp())
    fin_exclusivo = int(datetime.combine(hoy + timedelta(days=1), time.min, timezone.utc).timestamp())

    farmaceuticos = list(db.farmaceuticos.find(
        {"activo": True},
        {"_id": 1, "nombre": 1, "apellido": 1, "matricula": 1},
    ))

    with redis.pipeline(transaction=False) as pipe:
        for farm in farmaceuticos:
            pipe.zcount(f"{PREFIJO}{farm['_id']}", inicio, f"({fin_exclusivo}")
        cantidades = pipe.execute()

    resultado = [
        {
            "id_farmaceutico": f["_id"],
            "nombre": f["nombre"],
            "apellido": f["apellido"],
            "matricula": f["matricula"],
            "cantidad_ventas": int(cantidad),
        }
        for f, cantidad in zip(farmaceuticos, cantidades)
    ]
    return sorted(resultado, key=lambda f: (-f["cantidad_ventas"], f["id_farmaceutico"]))


if __name__ == "__main__":
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
    nombre_bd = os.getenv("MONGO_DB", "farmared")
    with MongoClient(mongo_uri) as mongo, Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    ) as redis:
        resultados = q05_ventas_farmaceuticos(mongo[nombre_bd], redis)
        print(f"Farmacéuticos activos: {len(resultados)}")
        print("Ventas registradas:", sum(f["cantidad_ventas"] for f in resultados))
        print("Farmacéuticos con cero ventas:", sum(f["cantidad_ventas"] == 0 for f in resultados))
        for farmaceutico in resultados:
            pprint(farmaceutico)
