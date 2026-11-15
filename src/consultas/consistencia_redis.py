"""Control de frescura de proyecciones Redis de FarmaRed.

No reconstruye automáticamente: las escrituras deben sincronizarse con el
servicio de publicación. Fallar con mensaje explícito evita reportes obsoletos.
"""
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo


def verificar_proyecciones(db, redis):
    """Impide lecturas de proyecciones inexistentes o con eventos pendientes."""
    marca = 'farmared:meta:reconstruccion'
    if not redis.exists(marca):
        raise RuntimeError('Redis no fue construido; ejecutar python scripts/construir_redis.py')
    pendientes = db.ventas.count_documents({'redis_sync': 'pendiente'}, limit=1)
    if pendientes:
        raise RuntimeError('Redis desactualizado: existen ventas pendientes de sincronización. '
                           'Ejecutar python scripts/sincronizar_redis.py')


def verificar_mes_sin_ventas(db, mes):
    """Distingue mes verdaderamente vacío de clave Redis faltante por error."""
    anio, numero = map(int, mes.split('-'))
    desde = datetime(anio, numero, 1, tzinfo=timezone.utc)
    hasta = datetime(anio + (numero == 12), numero % 12 + 1, 1, tzinfo=timezone.utc)
    hay = db.ventas.count_documents({
        'estado': 'Completada',
        'fecha': {'$gte': desde, '$lt': hasta}
    }, limit=1)
    return not hay
