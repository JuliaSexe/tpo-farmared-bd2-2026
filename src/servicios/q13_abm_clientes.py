"""Q13 – ABM de clientes de FarmaRed (MongoDB).

Alta: valida identificador y DNI únicos.
Modificación: permite cambiar únicamente datos de contacto y cobertura.
Baja lógica: marca activo=False sin borrar el historial.

Motor: MongoDB. No modifica proyecciones de Redis.
Ejecutar desde la raíz del repositorio (ver comandos de ejemplo).
"""

import argparse
import os
from pprint import pprint

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


CAMPOS_MODIFICABLES = (
    "email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado"
)


def verificar_texto(campo, valor):
    """Valida los valores de texto obligatorios conservando su tipo String."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} no puede estar vacío")
    return valor.strip()


def alta_cliente(db, datos):
    """Inserta un cliente activo; devuelve el documento creado.

    La unicidad de _id y DNI se protege mediante índices de MongoDB.
    """
    obligatorios = (
        "id_cliente", "nombre", "apellido", "dni", "email", "telefono",
        "ciudad", "provincia", "obra_social"
    )
    documento = {campo: verificar_texto(campo, datos[campo]) for campo in obligatorios}
    documento["_id"] = documento["id_cliente"]
    documento["nro_afiliado"] = (
        verificar_texto("nro_afiliado", datos["nro_afiliado"])
        if datos.get("nro_afiliado") else None
    )
    documento["activo"] = True

    try:
        db.clientes.insert_one(documento)
    except DuplicateKeyError as exc:
        raise ValueError("No se pudo dar el alta: ID o DNI ya registrado") from exc

    return db.clientes.find_one({"_id": documento["_id"]}, {"_id": 0})


def modificar_cliente(db, id_cliente, cambios):
    """Modifica solo contacto/cobertura; devuelve el documento actualizado."""
    id_cliente = verificar_texto("id_cliente", id_cliente)
    if not cambios:
        raise ValueError("Indicá al menos un campo para modificar")
    desconocidos = set(cambios) - set(CAMPOS_MODIFICABLES)
    if desconocidos:
        raise ValueError(f"Campos no modificables: {sorted(desconocidos)}")

    actualizaciones = {}
    for campo, valor in cambios.items():
        # nro_afiliado admite None para representar ausencia de cobertura.
        if campo == "nro_afiliado" and (valor is None or not valor.strip()):
            actualizaciones[campo] = None
        else:
            actualizaciones[campo] = verificar_texto(campo, valor)

    documento = db.clientes.find_one_and_update(
        {"_id": id_cliente},
        {"$set": actualizaciones},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if documento is None:
        raise ValueError(f"No existe el cliente {id_cliente}")
    return documento


def baja_cliente(db, id_cliente):
    """Aplica baja lógica idempotente; devuelve el documento actualizado."""
    id_cliente = verificar_texto("id_cliente", id_cliente)
    documento = db.clientes.find_one_and_update(
        {"_id": id_cliente},
        {"$set": {"activo": False}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if documento is None:
        raise ValueError(f"No existe el cliente {id_cliente}")
    return documento


def main():
    parser = argparse.ArgumentParser(description="Q13: ABM de clientes FarmaRed")
    sub = parser.add_subparsers(dest="accion", required=True)

    alta = sub.add_parser("alta", help="Crear cliente")
    for campo in (
        "id_cliente", "nombre", "apellido", "dni", "email", "telefono",
        "ciudad", "provincia", "obra_social"
    ):
        alta.add_argument("--" + campo.replace("_", "-"), required=True)
    alta.add_argument("--nro-afiliado", default=None)

    modificar = sub.add_parser("modificar", help="Actualizar contacto/cobertura")
    modificar.add_argument("--id-cliente", required=True)
    for campo in CAMPOS_MODIFICABLES:
        modificar.add_argument("--" + campo.replace("_", "-"), default=None)

    baja = sub.add_parser("baja", help="Dar de baja lógicamente")
    baja.add_argument("--id-cliente", required=True)

    args = parser.parse_args()
    uri = os.getenv(
        "MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0&directConnection=true"
    )
    nombre_bd = os.getenv("MONGO_DB", "farmared")

    with MongoClient(uri, serverSelectionTimeoutMS=5000) as mongo:
        db = mongo[nombre_bd]
        # Índice existente de la carga inicial: recrearlo es idempotente.
        db.clientes.create_index("dni", unique=True)
        try:
            if args.accion == "alta":
                datos = {campo: getattr(args, campo) for campo in (
                    "id_cliente", "nombre", "apellido", "dni", "email",
                    "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado"
                )}
                resultado = alta_cliente(db, datos)
            elif args.accion == "modificar":
                cambios = {campo: getattr(args, campo) for campo in CAMPOS_MODIFICABLES
                           if getattr(args, campo) is not None}
                resultado = modificar_cliente(db, args.id_cliente, cambios)
            else:
                resultado = baja_cliente(db, args.id_cliente)
        except ValueError as exc:
            parser.error(str(exc))

    print(f"OK Q13: {args.accion}")
    pprint(resultado)


if __name__ == "__main__":
    main()
