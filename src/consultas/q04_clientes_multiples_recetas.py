
import os
from pprint import pprint
from pymongo import MongoClient


def q04_clientes_multiples_recetas(db):
    pipeline = [
        {
            "$group": {
                "_id": "$id_cliente",
                "cantidad_recetas": {"$sum": 1}
            }
        },
        {
            "$match": {
                "cantidad_recetas": {"$gt": 1}
            }
        },
        {
            "$lookup": {
                "from": "clientes",
                "localField": "_id",
                "foreignField": "id_cliente",
                "as": "cliente"
            }
        },
        {
            "$unwind": "$cliente"
        },
        {
            "$project": {
                "_id": 0,
                "id_cliente": "$_id",
                "nombre": "$cliente.nombre",
                "apellido": "$cliente.apellido",
                "cantidad_recetas": 1
            }
        },
        {
            "$sort": {
                "cantidad_recetas": -1,
                "id_cliente": 1
            }
        }
    ]

    return list(db.recetas.aggregate(pipeline))


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        resultados = q04_clientes_multiples_recetas(
            client[nombre_bd]
        )

        print(
            f"Clientes con más de una receta: "
            f"{len(resultados)}"
        )

        for cliente in resultados:
            pprint(cliente)
# No vamos a excluir recetas vencidas o completadas, porque la consigna pide todas las recetas registradas.