"""Prueba de integración aislada de Q14 con receta opcional.

No modifica la base farmared ni Redis. Usa un MongoDB de prueba temporal,
crea una venta libre con receta adicional y verifica que no consuma dispensas.
La base se elimina al finalizar, aunque una comprobación falle.

    python scripts/probar_receta_opcional.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from pymongo import MongoClient

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.servicios import q14_registrar_venta as venta_modulo
from src.servicios.reglas_stock import ReglaNegocioError

URI = os.getenv('MONGO_URI', 'mongodb://mongo:27017/?replicaSet=rs0&directConnection=true')
BD_REAL = os.getenv('MONGO_DB', 'farmared')
BD_TEST = 'farmared_receta_opcional_' + uuid4().hex[:12]


def main():
    if BD_REAL == BD_TEST or not BD_TEST.startswith('farmared_receta_opcional_'):
        raise SystemExit('Nombre de base de prueba inseguro.')
    venta_modulo.BD = BD_TEST  # solamente en este proceso; no modifica archivos ni variables externas.
    print('Base temporal:', BD_TEST)
    print('Base real que NO se modifica:', BD_REAL)
    with MongoClient(URI, serverSelectionTimeoutMS=6000) as mongo:
        db = mongo[BD_TEST]
        if db.list_collection_names():
            raise SystemExit('La base temporal ya existía; se cancela sin modificarla.')
        try:
            db.clientes.insert_one({'_id':'C-OPT', 'id_cliente':'C-OPT', 'activo':True})
            db.sucursales.insert_one({'_id':'S-OPT', 'id_sucursal':'S-OPT', 'tipo':'Farmacia', 'activo':True})
            db.farmaceuticos.insert_one({'_id':'F-OPT', 'id_farmaceutico':'F-OPT', 'id_sucursal':'S-OPT', 'activo':True})
            db.productos.insert_one({'_id':'P-OPT', 'id_producto':'P-OPT', 'condicion_venta':'Venta libre', 'precio_unit':1000, 'activo':True})
            db.stock_lotes.insert_one({'_id':'L-OPT', 'id_lote':'L-OPT', 'id_sucursal':'S-OPT', 'id_producto':'P-OPT', 'unidades':3,
                                       'vencimiento':datetime.now(timezone.utc)+timedelta(days=365)})
            db.recetas.insert_one({'_id':'R-OPT', 'id_receta':'R-OPT', 'id_cliente':'C-OPT', 'estado':'Vencida',
                                   'tipo':'Simple', 'dispensas_autorizadas':1, 'dispensas_realizadas':0,
                                   'proxima_dispensa':None})
            resultado = venta_modulo.registrar_venta(mongo,'V-OPT','C-OPT','F-OPT','Efectivo',
                                                     [{'id_producto':'P-OPT','cantidad':1}],id_receta='R-OPT')
            guardada = db.ventas.find_one({'_id':'V-OPT'})
            receta = db.recetas.find_one({'_id':'R-OPT'})
            lote = db.stock_lotes.find_one({'_id':'L-OPT'})
            assert resultado['total']==1000
            assert guardada['tipo']=='Venta libre' and guardada['id_receta']=='R-OPT'
            assert guardada['stock_aplicado'] is True
            assert receta['estado']=='Vencida' and receta['dispensas_realizadas']==0
            assert lote['unidades']==2
            print('OK: venta libre con receta opcional registrada.')
            print('OK: stock descontado una vez y dispensa de receta sin modificaciones.')
            try:
                venta_modulo.registrar_venta(mongo,'V-OPT-BAD','C-OPT','F-OPT','Efectivo',
                                             [{'id_producto':'P-OPT','cantidad':1}],id_receta='R-INEXISTENTE')
            except ReglaNegocioError:
                assert db.ventas.find_one({'_id':'V-OPT-BAD'}) is None
                print('OK: referencia a receta inexistente rechazada sin crear venta.')
            else:
                raise AssertionError('Se aceptó una receta inexistente.')
            print('OK: prueba de integración completada.')
        finally:
            mongo.drop_database(BD_TEST)
            print('Base temporal eliminada; MongoDB real y Redis no se modificaron.')


if __name__=='__main__':
    main()
