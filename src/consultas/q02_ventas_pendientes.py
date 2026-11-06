import os
from pprint import pprint
from pymongo import MongoClient


def q02_ventas_pendientes(db):
    pipeline = [
        {
            "$match": {
                "estado": "Pendiente"
            }
        },
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
            "$lookup": {
                "from": "sucursales",
                "localField": "farmaceutico.id_sucursal",
                "foreignField": "id_sucursal",
                "as": "sucursal"
            }
        },
        {
            "$unwind": "$sucursal"
        },
        {
            "$project": {
                "_id": 0,
                "id_venta": 1,
                "fecha": 1,
                "total": 1,
                "farmaceutico": {
                    "nombre": "$farmaceutico.nombre",
                    "apellido": "$farmaceutico.apellido",
                    "matricula": "$farmaceutico.matricula"
                },
                "sucursal": {
                    "nombre": "$sucursal.nombre",
                    "ciudad": "$sucursal.ciudad",
                    "provincia": "$sucursal.provincia"
                }
            }
        },
        {
            "$sort": {
                "fecha": 1,
                "id_venta": 1
            }
        }
    ]

    return list(db.ventas.aggregate(pipeline))


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        resultados = q02_ventas_pendientes(
            client[nombre_bd]
        )

        print(f"Ventas pendientes: {len(resultados)}")

        for venta in resultados:
            pprint(venta)
