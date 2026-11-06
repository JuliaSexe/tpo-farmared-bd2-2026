
import os
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
from pprint import pprint
from pymongo import MongoClient


def q05_ventas_farmaceuticos(db):
    # Calcular 60 días calendario, incluyendo hoy.
    hoy = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).date()

    inicio = datetime.combine(
        hoy - timedelta(days=59),
        time.min,
        tzinfo=timezone.utc
    )

    fin = datetime.combine(
        hoy + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc
    )

    pipeline = [
        {
            "$match": {"activo": True}
        },
        {
            "$lookup": {
                "from": "ventas",
                "let": {
                    "farm_id": "$id_farmaceutico"
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$eq": [
                                    "$id_farmaceutico",
                                    "$$farm_id"
                                ]
                            },
                            "fecha": {
                                "$gte": inicio,
                                "$lt": fin
                            },
                            "estado": {"$ne": "Anulada"}
                        }
                    },
                    {
                        "$count": "cantidad"
                    }
                ],
                "as": "resumen"
            }
        },
        {
            "$project": {
                "_id": 0,
                "id_farmaceutico": 1,
                "nombre": 1,
                "apellido": 1,
                "matricula": 1,
                "cantidad_ventas": {
                    "$ifNull": [
                        {
                            "$arrayElemAt": [
                                "$resumen.cantidad", 0
                            ]
                        },
                        0
                    ]
                }
            }
        },
        {
            "$sort": {
                "cantidad_ventas": -1,
                "id_farmaceutico": 1
            }
        }
    ]

    return list(db.farmaceuticos.aggregate(pipeline))


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        resultados = q05_ventas_farmaceuticos(
            client[nombre_bd]
        )

        print(f"Farmacéuticos activos: {len(resultados)}")
        print(
            "Ventas registradas:",
            sum(f["cantidad_ventas"] for f in resultados)
        )

        for farmaceutico in resultados:
            pprint(farmaceutico)
