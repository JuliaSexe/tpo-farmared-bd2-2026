
import os
import argparse
from pprint import pprint
from pymongo import MongoClient


def q03_historial_cliente(db, id_cliente):
    # Verificar que el cliente exista.
    cliente = db.clientes.find_one(
        {"_id": id_cliente},
        {"_id": 0}
    )

    if cliente is None:
        raise ValueError("El cliente no existe")

    # Obtener todas sus ventas, sin filtrar estados.
    ventas = list(db.ventas.find(
        {"id_cliente": id_cliente},
        {"_id": 0}
    ))

    # Obtener todas sus recetas.
    recetas = list(db.recetas.find(
        {"id_cliente": id_cliente},
        {"_id": 0}
    ))

    historial = []

    for venta in ventas:
        historial.append({
            "tipo_registro": "Venta",
            "fecha_evento": venta["fecha"],
            "datos": venta
        })

    for receta in recetas:
        historial.append({
            "tipo_registro": "Receta",
            "fecha_evento": receta["fecha_emision"],
            "datos": receta
        })

    # Ordenar ambos tipos de registros por fecha.
    historial.sort(
        key=lambda registro: (
            registro["fecha_evento"],
            registro["tipo_registro"]
        )
    )

    return {
        "cliente": cliente,
        "cantidad_ventas": len(ventas),
        "cantidad_recetas": len(recetas),
        "historial": historial
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("id_cliente")
    args = parser.parse_args()

    uri = os.getenv("MONGO_URI")
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri) as client:
        resultado = q03_historial_cliente(
            client[nombre_bd],
            args.id_cliente
        )

        pprint(resultado)
