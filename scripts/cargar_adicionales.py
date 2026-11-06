"""Carga idempotente de datos de prueba NUEVOS y separados de los originales.

Uso (desde la raíz del repositorio en Codespaces):
    python scripts/cargar_adicionales.py

- 9 CSV adicionales, >=10 registros por CSV.
- 8 colecciones MongoDB: detalle_ventas va embebido en ventas.
- No sobreescribe documentos existentes.
- No modifica Redis ni descuenta stock de ventas historicas de prueba.
- Requiere MongoDB rs0 configurado por el entorno existente.
"""
import csv
import os
from pathlib import Path

from pymongo import MongoClient, UpdateOne

# Reutilizamos EXACTAMENTE las reglas de conversión, ids y embedding de la
# carga original para que los datos nuevos conserven el mismo modelo físico.
from cargar_originales import PK, convertir, comprobar_referencias, preparar_ventas

RUTA = Path(__file__).resolve().parents[1] / 'data' / 'adicionales'
URI = os.getenv('MONGO_URI', 'mongodb://mongo:27017/?replicaSet=rs0&directConnection=true')
BD = os.getenv('MONGO_DB', 'farmared')


def leer_adicional(nombre):
    ruta = RUTA / f'{nombre}.csv'
    if not ruta.is_file():
        raise FileNotFoundError(f'Falta el CSV adicional {ruta}')
    with ruta.open('r', encoding='utf-8-sig', newline='') as archivo:
        filas = [{k: convertir(k, v) for k, v in fila.items()}
                 for fila in csv.DictReader(archivo)]
    ids = [fila[PK[nombre]] for fila in filas]
    if len(filas) < 10 or None in ids or len(set(ids)) != len(ids):
        raise ValueError(f'{nombre}: se requieren >=10 filas con IDs unicos no vacios')
    return filas


def verificar_escenarios(datos):
    nuevos_clientes = {c['id_cliente']: c for c in datos['clientes']}
    sucursales = {s['id_sucursal']: s for s in datos['sucursales']}
    farmaceuticos = {f['id_farmaceutico']: f for f in datos['farmaceuticos']}
    productos = {p['id_producto']: p for p in datos['productos']}
    recetas = {r['id_receta']: r for r in datos['recetas']}
    for venta in datos['ventas']:
        id_venta = venta['id_venta']
        farmaceutico = farmaceuticos[venta['id_farmaceutico']]
        sucursal = sucursales[farmaceutico['id_sucursal']]
        cliente = nuevos_clientes[venta['id_cliente']]
        if cliente['activo'] is not True or farmaceutico['activo'] is not True or sucursal['tipo'] != 'Farmacia':
            raise ValueError(f'{id_venta}: cliente, farmaceutico o farmacia no habilitados')
        if venta['tipo'] == 'Con receta':
            receta = recetas[venta['id_receta']]
            if receta['id_cliente'] != venta['id_cliente'] or venta['estado'] != 'Completada':
                raise ValueError(f'{id_venta}: receta o estado incoherente en prueba')
        elif venta['id_receta'] is not None:
            raise ValueError(f'{id_venta}: venta libre con receta inesperada')
        for detalle in [d for d in datos['detalle_ventas'] if d['id_venta'] == id_venta]:
            if not productos[detalle['id_producto']]['activo']:
                raise ValueError(f'{id_venta}: producto inactivo en venta adicional')
    for lote in datos['stock_lotes']:
        if lote['unidades'] < 0:
            raise ValueError('Lote con stock negativo')


def main():
    datos = {nombre: leer_adicional(nombre) for nombre in PK}
    comprobar_referencias(datos)  # Todas las referencias de estos CSV son internas al lote adicional.
    verificar_escenarios(datos)
    datos['ventas'] = preparar_ventas(datos)

    with MongoClient(URI, serverSelectionTimeoutMS=5000) as mongo:
        mongo.admin.command('ping')
        db = mongo[BD]
        # No ejecutar la carga adicional sin haber cargado previamente los CSV originales.
        for nombre in ('clientes', 'productos', 'ventas', 'stock_lotes'):
            if db[nombre].count_documents({}) == 0:
                raise RuntimeError(f'Falta la carga original: {nombre} esta vacia')
        nuevos = {}
        with mongo.start_session() as sesion:
            with sesion.start_transaction():
                for nombre in PK:
                    if nombre == 'detalle_ventas':
                        continue
                    pk = PK[nombre]
                    docs = [{'_id': fila[pk], **fila} for fila in datos[nombre]]
                    operaciones = [UpdateOne({'_id': d['_id']}, {'$setOnInsert': d}, upsert=True)
                                   for d in docs]
                    res = db[nombre].bulk_write(operaciones, ordered=True, session=sesion)
                    nuevos[nombre] = res.upserted_count
        print('Carga de datos adicionales completada (transaccion MongoDB).')
        for nombre in PK:
            if nombre != 'detalle_ventas':
                print(f'  {nombre}: {nuevos[nombre]} nuevos; {db[nombre].count_documents({})} total')
        print('  detalle_ventas: 11 items adicionales embebidos (no es coleccion)')
        print('  Redis NO se modifico; reconstruir: python scripts/construir_redis.py')
        print('  Si se repite, los documentos existentes NO se insertan ni se sobreescriben.')


if __name__ == '__main__':
    main()
