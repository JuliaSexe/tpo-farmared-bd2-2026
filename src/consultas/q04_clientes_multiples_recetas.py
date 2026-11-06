"""Q04: clientes con más de una receta (conteos materializados en Redis).

MongoDB: datos descriptivos del cliente. Redis Hash: total de recetas de
cualquier estado por id_cliente. Ejecutar construir_redis.py previamente.
"""
import os
from pprint import pprint

from pymongo import MongoClient
from redis import Redis

CLAVE = "farmared:recetas:conteo_por_cliente"
MARCA = "farmared:meta:reconstruccion"


def q04_clientes_multiples_recetas(db, redis):
    if not redis.exists(MARCA) or not redis.exists(CLAVE):
        raise RuntimeError("Índice Q04 no construido. Ejecutar python scripts/construir_redis.py")

    conteos = redis.hgetall(CLAVE)
    seleccionados = {
        id_cliente: int(cantidad)
        for id_cliente, cantidad in conteos.items()
        if int(cantidad) > 1
    }
    if not seleccionados:
        return []

    clientes = list(db.clientes.find(
        {"_id": {"$in": list(seleccionados)}},
        {"_id": 1, "nombre": 1, "apellido": 1},
    ))
    if len(clientes) != len(seleccionados):
        raise ValueError("Redis referencia clientes que no existen en MongoDB")

    resultado = [
        {
            "id_cliente": c["_id"],
            "nombre": c["nombre"],
            "apellido": c["apellido"],
            "cantidad_recetas": seleccionados[c["_id"]],
        }
        for c in clientes
    ]
    return sorted(resultado, key=lambda c: (-c["cantidad_recetas"], c["id_cliente"]))


if __name__ == "__main__":
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
    nombre_bd = os.getenv("MONGO_DB", "farmared")
    with MongoClient(mongo_uri) as mongo, Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    ) as redis:
        resultados = q04_clientes_multiples_recetas(mongo[nombre_bd], redis)
        print(f"Clientes con más de una receta: {len(resultados)}")
        for cliente in resultados:
            pprint(cliente)
