"""Ajuste controlado del vencimiento L019 en una base YA cargada.

Actualiza solamente si sigue en fecha inicial 2026-11-09, conserva unidades
actuales y NO restaura lotes consumidos. Luego reconstruir Redis. Ejecutar
con escrituras detenidas. En entorno limpio, no es necesario.
"""
import os
from datetime import datetime, timezone
from pymongo import MongoClient

URI = os.getenv('MONGO_URI', 'mongodb://mongo:27017/?replicaSet=rs0&directConnection=true')
BD = os.getenv('MONGO_DB', 'farmared')

with MongoClient(URI, serverSelectionTimeoutMS=5000) as client:
    db = client[BD]
    anterior = datetime(2026, 11, 9, tzinfo=timezone.utc)
    nuevo = datetime(2027, 2, 7, tzinfo=timezone.utc)
    res = db.stock_lotes.update_one(
        {'_id': 'L019', 'id_producto': 'PRD014', 'id_sucursal': 'S006', 'vencimiento': anterior},
        {'$set': {'vencimiento': nuevo}}
    )
    if res.modified_count:
        print('OK: L019 vencimiento 2027-02-07. Unidades preservadas.')
    else:
        lote = db.stock_lotes.find_one({'_id': 'L019'}, {'vencimiento': 1, 'unidades': 1})
        print(f'Sin cambios: L019 no tenía fecha inicial exacta o no existe. Estado: {lote}')
print('IMPORTANTE: reconstruir Redis con python scripts/construir_redis.py')
