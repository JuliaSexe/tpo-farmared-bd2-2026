
import os
from pprint import pprint
from pymongo import MongoClient
from redis import Redis


def q07_productos_mas_vendidos(db, redis):
    clave = "farmared:ranking:productos:unidades"

    # Obtener los 5 productos con más unidades.
    ranking = redis.zrevrange(
        clave,
        0,
        4,
        withscores=True
    )

    ids = [id_producto for id_producto, _ in ranking]

    # Recuperar nombres desde MongoDB.
    productos = db.productos.find(
        {"_id": {"$in": ids}},
        {"_id": 1, "nombre": 1}
    )

    nombres = {
        producto["_id"]: producto["nombre"]
        for producto in productos
    }

    resultados = []

    for posicion, (id_producto, unidades) in enumerate(
        ranking, start=1
    ):
        resultados.append({
            "posicion": posicion,
            "id_producto": id_producto,
            "nombre": nombres.get(id_producto),
            "unidades_vendidas": int(unidades)
        })

    return resultados


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        with Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True
        ) as redis:

            resultados = q07_productos_mas_vendidos(
                client[nombre_bd],
                redis
            )

            print("Top 5 productos más vendidos:")

            for producto in resultados:
                pprint(producto)
