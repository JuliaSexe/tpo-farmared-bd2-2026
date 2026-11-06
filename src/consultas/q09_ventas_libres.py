
import os
from pprint import pprint
from pymongo import MongoClient


def q09_ventas_libres(db):

    filtro = {
        "tipo": "Venta libre",
        "total": {"$lt": 5000},
        "estado": {"$ne": "Anulada"}
    }

    proyeccion = {
        "_id": 0,
        "id_venta": 1,
        "id_cliente": 1,
        "id_farmaceutico": 1,
        "fecha": 1,
        "tipo": 1,
        "medio_pago": 1,
        "total": 1,
        "estado": 1,
        "items": 1
    }

    resultados = db.ventas.find(
        filtro,
        proyeccion
    ).sort([
        ("fecha", 1),
        ("id_venta", 1)
    ])

    return list(resultados)


if __name__ == "__main__":

    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:

        resultados = q09_ventas_libres(
            client[nombre_bd]
        )

        print(
            f"Ventas libres menores a $5.000: "
            f"{len(resultados)}"
        )

        for venta in resultados:
            pprint(venta)
