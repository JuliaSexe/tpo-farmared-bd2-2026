"""Funciones puras para planificar un consumo FEFO (sin acceso a base de datos)."""
from collections import defaultdict
from datetime import datetime


class ReglaNegocioError(ValueError):
    """Una operación no cumple una regla de FarmaRed."""


def validar_items_y_agrupar(items):
    """Devuelve cantidades por producto; evita descontar dos veces un mismo producto."""
    if not isinstance(items, list) or not items:
        raise ReglaNegocioError("La venta requiere al menos un ítem")
    cantidades = defaultdict(int)
    for item in items:
        producto = item.get("id_producto")
        cantidad = item.get("cantidad")
        if not isinstance(producto, str) or not producto.strip():
            raise ReglaNegocioError("Cada ítem requiere un id_producto")
        if type(cantidad) is not int or cantidad <= 0:
            raise ReglaNegocioError(f"Cantidad inválida para {producto}")
        cantidades[producto] += cantidad
    return dict(cantidades)


def planificar_consumo_fefo(items, lotes_por_producto):
    """Planifica sin escribir: primero vencimiento, luego identificador de lote.

    Recibe items con id_producto y cantidad, y un diccionario con lotes ya
    filtrados por sucursal, vigencia y unidades > 0. La consulta de MongoDB
    que provee esos lotes es responsable de aplicar dichos filtros.

    Si falta stock de CUALQUIER producto, rechaza sin generar un plan parcial.
    """
    cantidades = validar_items_y_agrupar(items)
    plan = []
    for producto, solicitado in sorted(cantidades.items()):
        lotes = sorted(
            lotes_por_producto.get(producto, []),
            key=lambda l: (l["vencimiento"], str(l["_id"])),
        )
        disponible = sum(l["unidades"] for l in lotes)
        if disponible < solicitado:
            raise ReglaNegocioError(
                f"Stock insuficiente para {producto}: disponible={disponible}, solicitado={solicitado}"
            )
        pendiente = solicitado
        for lote in lotes:
            if not pendiente:
                break
            cantidad = min(pendiente, lote["unidades"])
            if cantidad > 0:
                plan.append({
                    "id_lote": str(lote["_id"]),
                    "id_producto": producto,
                    "cantidad": cantidad,
                })
                pendiente -= cantidad
    return plan
