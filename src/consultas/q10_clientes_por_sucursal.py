
import os
import argparse
from pprint import pprint
from pymongo import MongoClient


def q10_clientes_por_sucursal(db, id_sucursal):

    # Verificar que exista la sucursal.
    sucursal = db.sucursales.find_one({
        "_id": id_sucursal
    })

    if sucursal is None:
        raise ValueError("La sucursal no existe")

    pipeline = [
        {
            "$lookup": {
                "from": "farmaceuticos",
                "localField": "id_farmaceutico",
                "foreignField": "id_farmaceutico",
                "as": "farmaceutico"
            }
        },
        {
            "$unwind": "$farmaceutico"
        },
        {
            "$match": {
                "farmaceutico.id_sucursal": id_sucursal
            }
        },
        {
            "$group": {
                "_id": "$id_cliente"
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
            "$replaceRoot": {
                "newRoot": "$cliente"
            }
        },
        {
            "$project": {
                "_id": 0
            }
        },
        {
            "$sort": {
                "apellido": 1,
                "nombre": 1,
                "id_cliente": 1
            }
        }
    ]

    return list(db.ventas.aggregate(pipeline))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("id_sucursal")
    args = parser.parse_args()

    uri = os.getenv(
        "MONGO_URI",
        "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true"
    )

    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:

        resultados = q10_clientes_por_sucursal(
            client[nombre_bd],
            args.id_sucursal
        )

        print(
            f"Clientes atendidos en {args.id_sucursal}: "
            f"{len(resultados)}"
        )

        for cliente in resultados:
            pprint(cliente)
# estamos atribuyendo las ventas a la sucursal actual registrada para el farmacéutico, porque ventas.csv no contiene id_sucursal. Si un farmacéutico cambiara de sucursal, necesitaríamos guardar la sucursal histórica de cada venta. Esto podría ser una limitación