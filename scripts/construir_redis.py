"""Reconstruye las proyecciones de Redis a partir de MongoDB (FarmaRed).

Ejecutar desde la raíz del repositorio:
    python scripts/construir_redis.py

MongoDB es la fuente de verdad. Este proceso SOLO LEE MongoDB y reemplaza
las claves Redis propias de FarmaRed. No registra ventas ni descuenta stock.
La reconstrucción es idempotente: ejecutarla otra vez NO duplica resultados.

Versión de desarrollo: reconstrucción MANUAL, sin escrituras concurrentes.
Hasta implementar sincronización automática, volver a ejecutar después de
modificar recetas, ventas o lotes. Las consultas sobre Redis podrían quedar
atrasadas hasta la siguiente reconstrucción.
"""

import os
from collections import defaultdict
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from redis import Redis

URI = os.getenv(
    "MONGO_URI",
    "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true",
)
BD = os.getenv("MONGO_DB", "farmared")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

STOCK_UNIDADES = "farmared:stock:por_unidades"
STOCK_VENCIMIENTOS = "farmared:stock:por_vencimiento"
RANKING_PRODUCTOS = "farmared:ranking:productos:unidades"
PREFIJO_INGRESOS = "farmared:ingresos:farmaceutico:"

# Nuevas proyecciones para Q04 y Q05.
RECETAS_POR_CLIENTE = "farmared:recetas:conteo_por_cliente"  # Hash
PREFIJO_VENTAS_FARM = "farmared:ventas:farmaceutico:"  # Sorted Set por farmacéutico
MARCA_RECONSTRUCCION = "farmared:meta:reconstruccion"
ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")


def fecha_csv_a_score(valor):
    """Convierte fecha BSON del CSV a score de medianoche UTC.

    En este proyecto los CSV contienen fechas sin hora, importadas como
    00:00 UTC. Interpretamos la fecha en UTC para no cambiar de día.
    """
    if not isinstance(valor, datetime):
        raise ValueError(f"Se esperaba fecha datetime, recibido {valor!r}")
    return int(datetime.combine(valor.date(), time.min, tzinfo=timezone.utc).timestamp())


def calcular_proyecciones(lotes, ventas, farmaceuticos, recetas, mes_actual):
    """Prepara todas las estructuras a partir de datos de MongoDB, sin escribir."""
    unidades_por_lote = {}
    vencimientos_por_lote = {}
    for lote in lotes:
        lote_id = str(lote["_id"])
        unidades = lote["unidades"]
        if type(unidades) is not int or unidades < 0:
            raise ValueError(f"Unidades inválidas del lote {lote_id}: {unidades!r}")
        unidades_por_lote[lote_id] = unidades
        if unidades > 0:
            vencimientos_por_lote[lote_id] = fecha_csv_a_score(lote["vencimiento"])

    recetas_conteo = defaultdict(int)
    for receta in recetas:
        recetas_conteo[str(receta["id_cliente"])] += 1  # Todos los estados.

    unidades_por_producto = defaultdict(int)
    ingresos_por_mes = defaultdict(lambda: defaultdict(int))
    ventas_por_farmaceutico = defaultdict(dict)

    for venta in ventas:
        fecha = venta["fecha"]
        score = fecha_csv_a_score(fecha)
        farm_id = str(venta["id_farmaceutico"])
        estado = venta["estado"]

        # Q05: incluir Completada Y Pendiente; excluir solamente Anulada.
        if estado != "Anulada":
            ventas_por_farmaceutico[farm_id][str(venta["_id"])] = score

        # Q07 y Q11: solo ventas completadas.
        if estado != "Completada":
            continue
        mes = fecha.strftime("%Y-%m")
        total = venta["total"]
        if type(total) is not int or total < 0:
            raise ValueError(f"Total inválido de venta {venta['_id']}: {total!r}")
        ingresos_por_mes[mes][farm_id] += total

        for item in venta["items"]:
            cantidad = item["cantidad"]
            if type(cantidad) is not int or cantidad <= 0:
                raise ValueError(f"Cantidad inválida de venta {venta['_id']}")
            unidades_por_producto[str(item["id_producto"])] += cantidad

    # La Q11 debe poder mostrar ingresos cero para todos los farmacéuticos.
    for f in farmaceuticos:
        ingresos_por_mes[mes_actual].setdefault(str(f["_id"]), 0)

    return {
        "stock": unidades_por_lote,
        "vencimientos": vencimientos_por_lote,
        "ranking": dict(unidades_por_producto),
        "ingresos": {mes: dict(x) for mes, x in ingresos_por_mes.items()},
        "recetas_conteo": dict(recetas_conteo),
        "ventas_por_farm": dict(ventas_por_farmaceutico),
    }


def escribir_redis(redis, datos):
    """Publica las proyecciones con MULTI/EXEC exclusivamente en Redis.

    SCAN y lectura de MongoDB no forman parte de una transacción distribuida.
    No ejecutar dos reconstrucciones a la vez ni durante escrituras en MongoDB.
    """
    ingresos_viejos = list(redis.scan_iter(match=f"{PREFIJO_INGRESOS}*"))
    ventas_viejas = list(redis.scan_iter(match=f"{PREFIJO_VENTAS_FARM}*"))
    claves = list(dict.fromkeys([
        STOCK_UNIDADES,
        STOCK_VENCIMIENTOS,
        RANKING_PRODUCTOS,
        RECETAS_POR_CLIENTE,
        MARCA_RECONSTRUCCION,
        *ingresos_viejos,
        *ventas_viejas,
    ]))
    with redis.pipeline(transaction=True) as pipe:
        pipe.delete(*claves)
        if datos["stock"]:
            pipe.zadd(STOCK_UNIDADES, datos["stock"])
        if datos["vencimientos"]:
            pipe.zadd(STOCK_VENCIMIENTOS, datos["vencimientos"])
        if datos["ranking"]:
            pipe.zadd(RANKING_PRODUCTOS, datos["ranking"])
        if datos["recetas_conteo"]:
            pipe.hset(RECETAS_POR_CLIENTE, mapping=datos["recetas_conteo"])
        for farm_id, ventas in sorted(datos["ventas_por_farm"].items()):
            if ventas:
                pipe.zadd(f"{PREFIJO_VENTAS_FARM}{farm_id}", ventas)
        for mes, montos in sorted(datos["ingresos"].items()):
            if montos:
                pipe.hset(f"{PREFIJO_INGRESOS}{mes}", mapping=montos)
        pipe.hset(MARCA_RECONSTRUCCION, mapping={
            "fecha_utc": datetime.now(timezone.utc).isoformat(),
            "origen": "mongodb",
            "modo": "manual",
        })
        pipe.execute()


def main():
    mes_actual = datetime.now(ZONA_HORARIA).strftime("%Y-%m")
    with MongoClient(URI, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
        db = client[BD]
        lotes = list(db.stock_lotes.find({}, {"_id": 1, "unidades": 1, "vencimiento": 1}))
        ventas = list(db.ventas.find({}, {
            "_id": 1, "estado": 1, "fecha": 1, "total": 1,
            "id_farmaceutico": 1, "items": 1,
        }))
        farmaceuticos = list(db.farmaceuticos.find({}, {"_id": 1}))
        recetas = list(db.recetas.find({}, {"_id": 1, "id_cliente": 1}))

    if not lotes or not ventas or not farmaceuticos or not recetas:
        raise RuntimeError("Faltan datos. Ejecutar antes los scripts de carga MongoDB.")

    datos = calcular_proyecciones(lotes, ventas, farmaceuticos, recetas, mes_actual)
    with Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True) as redis:
        redis.ping()
        escribir_redis(redis, datos)
        print("OK: proyecciones Redis reconstruidas desde MongoDB.")
        print(f"  Stock: {redis.zcard(STOCK_UNIDADES)} lotes")
        print(f"  Vencimientos: {redis.zcard(STOCK_VENCIMIENTOS)} lotes")
        print(f"  Ranking: {redis.zcard(RANKING_PRODUCTOS)} productos")
        print(f"  Ingresos: {len(datos['ingresos'])} meses")
        print(f"  Q04: {redis.hlen(RECETAS_POR_CLIENTE)} clientes con recetas")
        print(f"  Q05: {len(datos['ventas_por_farm'])} farmacéuticos con ventas no anuladas indexadas")
        print("  Redis NO descuenta stock ni modifica MongoDB.")


if __name__ == "__main__":
    main()
