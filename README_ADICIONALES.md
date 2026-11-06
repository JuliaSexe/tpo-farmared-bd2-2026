# FarmaRed — datos adicionales sintéticos (pruebas)

Todos los nuevos nombres, documentos y datos identificatorios fueron **creados artificialmente para el TPO**. No provienen de la cátedra y no son datos reales. Se mantienen en `data/adicionales/`, por separado de `data/originales/`.

## Contenido

- 9 archivos CSV con 10 o 11 filas cada uno: 10 clientes, 10 sucursales, 10 farmacéuticos, 10 proveedores, 10 productos, 11 lotes, 10 recetas, 10 ventas y 11 detalles.
- Los 11 detalles se embeben dentro de las 10 ventas, porque la colección MongoDB `ventas` es documental.
- Casos: farmacias activas e inactivas, droguería, clientes sin ventas, farmacéuticos con cero ventas, recetas atrasadas y vencidas, ventas pendientes y anuladas, ventas completadas de noviembre de 2026, lotes con stock bajo, agotados y vencidos.
- FEFO: `L019` y `L020` contienen el mismo producto `PRD014` en `S006` y vencen en fechas distintas. Permiten probar q15 con una venta nueva que requiera unidades de ambos lotes.

## Cargar (solo después de cargar los originales)

```bash
python scripts/cargar_adicionales.py
python scripts/inspeccionar_bases.py
python scripts/construir_redis.py
```

La carga en MongoDB es idempotente mediante `upsert` con `$setOnInsert` y transacción. Las ventas adicionales completadas son **históricas de prueba** y se importan como `stock_aplicado=True` sin descontar de nuevo el inventario, que representa la fotografía inicial para la prueba. Las ventas pendientes/anuladas tienen `stock_aplicado=False` y no computan ingresos ni consumo de stock.

**Importante:** la carga de nuevas ventas q14/q15 será independiente de estos CSV de prueba. No ejecutar la carga adicional simultáneamente con operaciones del sistema.

## Resultados esperados de MongoDB (sin otras cargas)

| Colección | Registros totales |
|---|---:|
| clientes | 18 |
| sucursales | 15 |
| farmaceuticos | 17 |
| proveedores | 15 |
| productos | 23 |
| stock_lotes | 29 |
| recetas | 19 |
| ventas | 26 |
| **Total** | **162** |

Las ventas contienen 33 ítems embebidos en total (22 originales + 11 nuevos).

Las fechas de referencia de las pruebas están ubicadas en septiembre–noviembre de 2026. Las consultas `hoy`, `mes actual` y `últimos N días` deberán usar la fecha del sistema y por lo tanto sus resultados variarán en ejecuciones posteriores.
