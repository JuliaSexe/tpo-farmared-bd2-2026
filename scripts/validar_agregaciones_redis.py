"""Contrasta Q04 y Q05 calculadas desde MongoDB con sus índices Redis.

No escribe datos. Útil como prueba de consistencia después de reconstruir Redis.
Ejecutar desde raíz del proyecto: python scripts/validar_agregaciones_redis.py
"""
import os
from collections import Counter
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from redis import Redis

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
MONGO_DB = os.getenv("MONGO_DB", "farmared")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


def main():
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    inicio = datetime.combine(hoy - timedelta(days=59), time.min, tzinfo=timezone.utc)
    fin = datetime.combine(hoy + timedelta(days=1), time.min, tzinfo=timezone.utc)

    with MongoClient(MONGO_URI) as mongo, Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
    ) as r:
        db = mongo[MONGO_DB]
        # Q04: todos los estados de recetas, sin excluir clientes.
        conteos_mongo = {
            str(x["_id"]): x["total"]
            for x in db.recetas.aggregate([
                {"$group": {"_id": "$id_cliente", "total": {"$sum": 1}}}
            ])
        }
        conteos_redis = {
            cliente: int(total)
            for cliente, total in r.hgetall("farmared:recetas:conteo_por_cliente").items()
        }
        assert conteos_mongo == conteos_redis, (
            f"Q04 no coincide: Mongo={conteos_mongo}, Redis={conteos_redis}"
        )
        print("OK Q04: conteos de recetas por cliente coinciden con MongoDB")

        # Q05: todos los farmacéuticos activos, incluidos los que tienen 0.
        farmaceuticos = list(db.farmaceuticos.find({"activo": True}, {"_id": 1}))
        ventas_mongo = Counter(v["id_farmaceutico"] for v in db.ventas.find(
            {"estado": {"$ne": "Anulada"}, "fecha": {"$gte": inicio, "$lt": fin}},
            {"id_farmaceutico": 1},
        ))
        errores = []
        total = 0
        ceros = 0
        for f in farmaceuticos:
            id_farm = str(f["_id"])
            observado = r.zcount(
                f"farmared:ventas:farmaceutico:{id_farm}",
                int(inicio.timestamp()), f"({int(fin.timestamp())}",
            )
            esperado = ventas_mongo[id_farm]
            if observado != esperado:
                errores.append((id_farm, esperado, observado))
            total += observado
            ceros += observado == 0
        assert not errores, f"Q05 difiere (farmacéutico, Mongo, Redis): {errores}"
        print(f"OK Q05: {len(farmaceuticos)} farmacéuticos activos; "
              f"{total} ventas; {ceros} con cero. Fecha: {hoy}")


if __name__ == "__main__":
    main()
