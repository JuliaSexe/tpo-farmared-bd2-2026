# Pruebas de concurrencia de FarmaRed

Desde la raíz del Codespace, ejecutar:

```bash
python scripts/probar_concurrencia.py
```

El script **no modifica `farmared` ni Redis**. Crea una base de MongoDB temporal llamada
`farmared_concurrencia_<ID_aleatorio>`, inserta entidades de prueba, ejecuta ventas
concurrentes y elimina la base temporal mediante `finally`, incluso si una comprobación falla.

## Escenarios

**A. Dos ventas diferentes compiten por stock.** Hay 10 unidades del mismo lote y dos
ventas concurrentes solicitan 7 unidades cada una. Resultado esperado: una venta
confirmada y otra rechazada, una única venta persistida y stock final igual a 3.

**B. Dos intentos con el mismo ID de venta.** Hay 10 unidades y ambos intentan vender
3 usando el mismo identificador. Resultado esperado: una venta confirmada, otra
rechazada por duplicación, una única venta persistida y stock final igual a 7.

Ambos casos ejecutan `registrar_venta()` y `aplicar_stock_venta()` reales con transacciones
MongoDB, pero **no invocan la sincronización Redis** porque la base de prueba es efímera.

Estas son pruebas funcionales simultáneas, no un benchmark de rendimiento ni una
prueba de estrés. Repetirlas permite observar conflictos, pero no demuestra ausencia
absoluta de problemas de concurrencia en todas las condiciones.
