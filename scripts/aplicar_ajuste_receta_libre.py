"""Ajuste de Q14: permitir receta OPCIONAL en una venta de productos libres.

Ejecutar desde la raíz del repositorio FarmaRed:
    python scripts/aplicar_ajuste_receta_libre.py

La receta opcional debe existir y pertenecer al cliente. No debe ser Vigente
porque la venta de un producto libre no depende de la prescripción, y no se
consume ninguna dispensa. Se conserva id_receta como referencia informativa.

El script modifica solamente el bloque puntual en q14_registrar_venta.py.
"""
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / 'src' / 'servicios' / 'q14_registrar_venta.py'
ANTERIOR = '''        if id_receta and not necesita_receta:
            raise ReglaNegocioError("La venta solo contiene productos libres: no debe afectar una receta")
'''
NUEVO = '''        if id_receta and not necesita_receta:
            # Una receta opcional no convierte un producto libre en obligatorio bajo receta.
            # Se verifica la referencia pero no se modifica el estado ni sus dispensas.
            receta_opcional = db.recetas.find_one({"_id": id_receta}, session=session)
            if not receta_opcional or receta_opcional.get("id_cliente") != id_cliente:
                raise ReglaNegocioError(
                    "La receta opcional debe existir y pertenecer al cliente"
                )
'''


def main():
    if not RUTA.exists():
        raise SystemExit(f'ERROR: no se encontró {RUTA}. Ejecutar desde la raíz del repositorio.')
    texto = RUTA.read_text(encoding='utf-8')
    if NUEVO in texto:
        print('El ajuste ya está aplicado; no se modificó nada.')
        return
    if texto.count(ANTERIOR) != 1:
        raise SystemExit('ERROR: el bloque esperado no coincide. No se modificó Q14.')
    RUTA.write_text(texto.replace(ANTERIOR, NUEVO, 1), encoding='utf-8')
    print('OK: Q14 admite una receta opcional de un cliente en ventas libres.')
    print('La receta se conserva como referencia y no se modifican las dispensas.')
    print('Ejecutar: python scripts/probar_receta_opcional.py')


if __name__ == '__main__':
    main()
