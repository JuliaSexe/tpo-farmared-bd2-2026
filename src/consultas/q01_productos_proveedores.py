
import os
from pprint import pprint
from pymongo import MongoClient


def q01_productos_proveedores(db):
    pipeline = [
        {
            "$match": {"activo": True}
        },
        {
            "$lookup": {
                "from": "proveedores",
                "localField": "id_proveedor",
                "foreignField": "id_proveedor",
                "as": "proveedor"
            }
        },
        {
            "$unwind": "$proveedor"
        },
        {
            "$project": {
                "_id": 0,
                "id_producto": 1,
                "nombre": 1,
                "principio_activo": 1,
                "categoria": 1,
                "presentacion": 1,
                "condicion_venta": 1,
                "precio_unit": 1,
                "activo": 1,
                "proveedor": 1
            }
        },
        {
            "$sort": {"id_producto": 1}
        }
    ]

    return list(db.productos.aggregate(pipeline))


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        resultados = q01_productos_proveedores(client[nombre_bd])

        print(f"Productos encontrados: {len(resultados)}")

        for producto in resultados:
            pprint(producto)
