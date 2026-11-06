
import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pprint import pprint
from pymongo import MongoClient


def q12_clientes_sin_ventas(db):

    hoy = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).date()

    # Mismo día del año anterior.
    try:
        inicio_dia = hoy.replace(year=hoy.year - 1)
    except ValueError:
        # Caso especial: 29 de febrero.
        inicio_dia = hoy.replace(
            year=hoy.year - 1, day=28
        )

    # Las fechas del CSV se guardaron a medianoche UTC.
    inicio = datetime.combine(
        inicio_dia, time.min, tzinfo=timezone.utc
    )

    fin = datetime.combine(
        hoy + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc
    )

    pipeline = [
        {
            "$lookup": {
                "from": "ventas",
                "let": {
                    "cliente_id": "$id_cliente"
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$eq": [
                                    "$id_cliente",
                                    "$$cliente_id"
                                ]
                            },
                            "fecha": {
                                "$gte": inicio,
                                "$lt": fin
                            }
                        }
                    },
                    {
                        "$limit": 1
                    }
                ],
                "as": "ventas_recientes"
            }
        },
        {
            "$match": {
                "ventas_recientes": {"$eq": []}
            }
        },
        {
            "$project": {
                "_id": 0,
                "id_cliente": 1,
                "nombre": 1,
                "apellido": 1,
                "activo": 1,
                "ciudad": 1
            }
        },
        {
            "$sort": {
                "id_cliente": 1
            }
        }
    ]

    return list(db.clientes.aggregate(pipeline))


if __name__ == "__main__":

    uri = os.getenv(
        "MONGO_URI",
        "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true"
    )

    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:

        resultados = q12_clientes_sin_ventas(
            client[nombre_bd]
        )

        print(
            f"Clientes sin ventas en el último año: "
            f"{len(resultados)}"
        )

        for cliente in resultados:
            pprint(cliente)
