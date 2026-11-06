"""Comprueba conectividad y requisitos de configuración (no carga datos)."""
import os
import sys
from pymongo import MongoClient
from redis import Redis


def main():
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongo:27017/?replicaSet=rs0&directConnection=true')
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))

    try:
        with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as mongo:
            hello = mongo.admin.command('hello')
            assert hello.get('setName') == 'rs0', 'MongoDB no tiene replica set rs0'
            assert hello.get('isWritablePrimary'), 'MongoDB aún no es PRIMARY'
            print('OK: MongoDB accesible y replica set rs0 activo.')

        with Redis(host=redis_host, port=redis_port, socket_connect_timeout=5) as redis:
            assert redis.ping(), 'Redis no respondió al PING'
            aof = redis.config_get('appendonly').get('appendonly')
            assert aof == 'yes', 'Redis no tiene AOF habilitado'
            print('OK: Redis accesible y persistencia AOF habilitada.')

        print('Entorno listo. Siguiente etapa: carga de datos desde CSV.')
        return 0
    except Exception as exc:
        print(f'ERROR al verificar entorno: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
