
import os
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from pprint import pprint
from pymongo import MongoClient


def q06_recetas_atrasadas(db):

    # Fecha actual de Argentina.
    hoy = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).date()

    # Los CSV se almacenaron como fechas a medianoche UTC.
    limite = datetime.combine(
        hoy, time.min, tzinfo=timezone.utc
    )

    pipeline = [
        {
            "$match": {
                "tipo": "Tratamiento prolongado",
                "estado": "Vigente",
                "proxima_dispensa": {
                    "$lt": limite
                }
            }
        },
        {
            "$lookup": {
                "from": "clientes",
                "localField": "id_cliente",
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
                "cliente._id": 0
            }
        },
        {
            "$sort": {
                "proxima_dispensa": 1,
                "id_receta": 1
            }
        }
    ]

    return list(db.recetas.aggregate(pipeline))


if __name__ == "__main__":
    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        resultados = q06_recetas_atrasadas(
            client[nombre_bd]
        )

        print(f"Recetas atrasadas: {len(resultados)}")

        for receta in resultados:
            pprint(receta)
