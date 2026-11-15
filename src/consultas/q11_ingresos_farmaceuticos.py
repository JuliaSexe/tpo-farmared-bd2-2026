
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from src.consultas.consistencia_redis import verificar_proyecciones, verificar_mes_sin_ventas

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pprint import pprint

from pymongo import MongoClient
from redis import Redis


def q11_ingresos_farmaceuticos(db, redis):

    # Mes actual según la fecha de Argentina.
    """Propósito: ingresos del mes actual por farmacéutico, incluidos ceros.

        Parámetros: db (MongoDB), redis (Redis).
        Retorno: lista de farmacéuticos con ingresos mensuales.
        Motores: Redis (Hash), MongoDB (farmacéuticos/validación).
        """
    verificar_proyecciones(db, redis)
    mes_actual = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).strftime("%Y-%m")

    clave = (
        f"farmared:ingresos:farmaceutico:{mes_actual}"
    )

    if not redis.exists(clave):
        # Al iniciar un nuevo mes no existe Hash todavía: devolver ceros
        # SOLO si MongoDB confirma que no hay ventas Completada del mes.
        if not verificar_mes_sin_ventas(db, mes_actual):
            raise RuntimeError(
                "Hay ventas del mes en MongoDB pero falta la proyección Redis. "
                "Ejecutar python scripts/construir_redis.py"
            )

    # Redis devuelve los ingresos acumulados.
    ingresos = redis.hgetall(clave)

    # MongoDB devuelve los datos de los farmacéuticos.
    farmaceuticos = db.farmaceuticos.find(
        {},
        {
            "_id": 0,
            "id_farmaceutico": 1,
            "nombre": 1,
            "apellido": 1,
            "matricula": 1
        }
    )

    resultados = []

    for f in farmaceuticos:

        id_farmaceutico = f["id_farmaceutico"]

        resultados.append({
            "id_farmaceutico": id_farmaceutico,
            "nombre": f["nombre"],
            "apellido": f["apellido"],
            "matricula": f["matricula"],
            "mes": mes_actual,
            "ingresos_totales": int(
                ingresos.get(id_farmaceutico, 0)
            )
        })

    resultados.sort(
        key=lambda x: (
            -x["ingresos_totales"],
            x["id_farmaceutico"]
        )
    )

    return resultados


if __name__ == "__main__":

    uri = os.getenv(
        "MONGO_URI",
        "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true"
    )

    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as mongo:
        with Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True
        ) as redis:

            resultados = q11_ingresos_farmaceuticos(
                mongo[nombre_bd],
                redis
            )

            print(
                f"Farmacéuticos: {len(resultados)}"
            )

            print(
                "Ingresos totales del mes: $",
                sum(
                    f["ingresos_totales"]
                    for f in resultados
                )
            )

            for f in resultados:
                pprint(f)
