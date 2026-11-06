"""Reconstruye Redis de modo recuperable tras ventas nuevas (Q14/Q15).

No usa una colección adicional: las ventas nuevas tienen la marca
redis_sync='pendiente'. Dentro de un snapshot MongoDB lee los datos y la lista
de pendientes. Publica las proyecciones en Redis y SOLO entonces marca las
ventas como sincronizadas. Si Redis falla, queda la marca para reintentar.

Limitación: el lock coordina ESTE script, pero reconstruir_redis.py ejecutado
manualmente en paralelo podría interferir. Para escala productiva considerar
materialización incremental/CDC y un único publicador ordenado.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from redis import Redis

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.construir_redis import calcular_proyecciones, escribir_redis

URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
BD = os.getenv("MONGO_DB", "farmared")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


def sincronizar_pendientes():
    """Publica snapshot de MongoDB en Redis. Devuelve cantidad sincronizada."""
    with Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True) as redis:
        redis.ping()
        # Previene dos reconstrucciones simultáneas desde este mecanismo.
        with redis.lock("farmared:lock:sincronizar", timeout=120, blocking_timeout=20):
            with MongoClient(URI, serverSelectionTimeoutMS=6000) as client:
                db = client[BD]
                with client.start_session() as session:
                    session.start_transaction(read_concern=ReadConcern("snapshot"))
                    try:
                        pendientes = [x["_id"] for x in db.ventas.find(
                            {"redis_sync": "pendiente"}, {"_id": 1}, session=session)]
                        if not pendientes:
                            session.abort_transaction()
                            return 0
                        lotes = list(db.stock_lotes.find({}, {
                            "_id": 1, "unidades": 1, "vencimiento": 1
                        }, session=session))
                        ventas = list(db.ventas.find({}, {
                            "_id": 1, "estado": 1, "fecha": 1, "total": 1,
                            "id_farmaceutico": 1, "items": 1,
                        }, session=session))
                        farmaceuticos = list(db.farmaceuticos.find({}, {
                            "_id": 1
                        }, session=session))
                        recetas = list(db.recetas.find({}, {
                            "_id": 1, "id_cliente": 1
                        }, session=session))
                        session.commit_transaction()
                    except Exception:
                        if session.in_transaction:
                            session.abort_transaction()
                        raise

                mes_actual = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%Y-%m")
                datos = calcular_proyecciones(lotes, ventas, farmaceuticos, recetas, mes_actual)
                # Si no se completa esta instrucción, NO se desmarcan pendientes.
                escribir_redis(redis, datos)
                # Sólo se marcan las ventas incluidas en el snapshot publicado.
                res = db.ventas.update_many(
                    {"_id": {"$in": pendientes}, "redis_sync": "pendiente"},
                    {"$set": {"redis_sync": "sincronizado",
                               "redis_sync_en": datetime.now(timezone.utc)}}
                )
                return res.modified_count


def main():
    n = sincronizar_pendientes()
    print(f"OK: {n} venta(s) nueva(s) sincronizada(s) con Redis.")
    if n == 0:
        print("No había proyecciones pendientes por nuevas ventas.")


if __name__ == "__main__":
    main()
