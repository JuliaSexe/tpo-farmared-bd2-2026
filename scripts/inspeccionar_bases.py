"""Muestra qué colecciones y claves existen (útil al avanzar con las cargas)."""
import os
from pymongo import MongoClient
from redis import Redis

mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongo:27017/?replicaSet=rs0&directConnection=true')
db_name = os.getenv('MONGO_DB', 'farmared')
with MongoClient(mongo_uri) as client:
    db = client[db_name]
    nombres = db.list_collection_names()
    print(f'MongoDB / {db_name}:')
    if nombres:
        for nombre in sorted(nombres):
            print(f'  - {nombre}: {db[nombre].count_documents({})} documentos')
    else:
        print('  Sin colecciones: todavía no se cargaron los CSV.')

with Redis(host=os.getenv('REDIS_HOST', 'redis'), port=int(os.getenv('REDIS_PORT', '6379'))) as r:
    print(f'Redis: {r.dbsize()} claves')
