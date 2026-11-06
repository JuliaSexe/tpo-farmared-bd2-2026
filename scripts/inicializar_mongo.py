"""Inicializa de forma idempotente un replica set MongoDB de un único nodo.

Solo para desarrollo en Codespaces. No es una configuración de producción.
"""
import os
import sys
import time
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

MONGO_SEED = 'mongodb://mongo:27017/?directConnection=true'
REPLICA_SET_CONFIG = {
    '_id': 'rs0',
    'members': [{'_id': 0, 'host': 'mongo:27017'}],
}


def main():
    last_error = None
    for attempt in range(1, 61):
        try:
            with MongoClient(MONGO_SEED, serverSelectionTimeoutMS=2000) as mongo:
                mongo.admin.command('ping')
                try:
                    status = mongo.admin.command('replSetGetStatus')
                except OperationFailure as exc:
                    # MongoDB aún no fue configurado como replica set.
                    if exc.code != 94:
                        raise
                    print('MongoDB: iniciando el replica set rs0...')
                    mongo.admin.command({'replSetInitiate': REPLICA_SET_CONFIG})
                    status = None
                hello = mongo.admin.command('hello')
                if hello.get('isWritablePrimary'):
                    print('OK: MongoDB replica set rs0, nodo PRIMARY.')
                    return 0
                if attempt % 5 == 0:
                    print('MongoDB: esperando la elección de PRIMARY...')
        except PyMongoError as exc:
            last_error = exc
            if attempt % 5 == 0:
                print(f'MongoDB: intento {attempt} - {exc}')
        time.sleep(2)
    print(f'ERROR: MongoDB no está listo. Último error: {last_error}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
