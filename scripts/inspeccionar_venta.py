"""Verificación de venta y stock. Sólo lectura."""
import argparse
import os
from pprint import pprint
from pymongo import MongoClient


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--id-venta", required=True)
    p.add_argument("--id-sucursal", required=True)
    p.add_argument("--id-producto", required=True)
    p.add_argument("--id-receta", default=None)
    a=p.parse_args()
    uri=os.getenv("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true")
    with MongoClient(uri) as mongo:
        db=mongo[os.getenv("MONGO_DB", "farmared")]
        venta=db.ventas.find_one({"_id":a.id_venta})
        print("VENTA:")
        pprint(venta)
        print("LOTES:")
        for lote in db.stock_lotes.find({
            "id_sucursal":a.id_sucursal, "id_producto":a.id_producto
        }, {"_id":1,"unidades":1,"vencimiento":1}).sort([("vencimiento",1),("_id",1)]):
            pprint(lote)
        if a.id_receta:
            print("RECETA:")
            pprint(db.recetas.find_one({"_id":a.id_receta}))


if __name__ == "__main__":
    main()
