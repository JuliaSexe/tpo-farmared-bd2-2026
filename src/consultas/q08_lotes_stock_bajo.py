
import os
from pprint import pprint
from pymongo import MongoClient
from redis import Redis


def q08_lotes_stock_bajo(db, redis):
    clave = "farmared:stock:por_unidades"

    if not redis.exists(clave):
        raise RuntimeError(
            "El índice de stock no existe en Redis"
        )

    # 1. Redis identifica lotes con menos de 50 unidades.
    ids_lotes = redis.zrangebyscore(
        clave,
        "-inf",
        "(50"
    )

    if not ids_lotes:
        return []

    # 2. MongoDB recupera información relacionada.
    pipeline = [
        {
            "$match": {
                "_id": {"$in": ids_lotes}
            }
        },
        {
            "$lookup": {
                "from": "productos",
                "localField": "id_producto",
                "foreignField": "id_producto",
                "as": "producto"
            }
        },
        {"$unwind": "$producto"},
        {
            "$lookup": {
                "from": "sucursales",
                "localField": "id_sucursal",
                "foreignField": "id_sucursal",
                "as": "sucursal"
            }
        },
        {"$unwind": "$sucursal"},
        {
            "$lookup": {
                "from": "proveedores",
                "localField": "producto.id_proveedor",
                "foreignField": "id_proveedor",
                "as": "proveedor"
            }
        },
        {"$unwind": "$proveedor"},
        {
            "$project": {
                "_id": 0,
                "id_lote": 1,
                "nro_lote": 1,
                "unidades": 1,
                "vencimiento": 1,
                "producto": {
                    "id_producto": "$producto.id_producto",
                    "nombre": "$producto.nombre"
                },
                "sucursal": {
                    "id_sucursal": "$sucursal.id_sucursal",
                    "nombre": "$sucursal.nombre"
                },
                "proveedor": {
                    "id_proveedor": "$proveedor.id_proveedor",
                    "razon_social": "$proveedor.razon_social"
                }
            }
        },
        {
            "$sort": {
                "unidades": 1,
                "id_lote": 1
            }
        }
    ]

    return list(db.stock_lotes.aggregate(pipeline))


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as mongo:
        with Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True
        ) as redis:

            resultados = q08_lotes_stock_bajo(
                mongo[nombre_bd],
                redis
            )

            print(f"Lotes con menos de 50 unidades: {len(resultados)}")

            for lote in resultados:
                pprint(lote)
# Tambien pueden aparecer lotes vencidos, porque Q08 no exige excluirlos.