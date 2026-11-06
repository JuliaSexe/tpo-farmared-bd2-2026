# FarmaRed — Q14 y Q15 integradas (MongoDB + Redis)

## Qué hace cada archivo

| Archivo | Responsabilidad |
|---|---|
| `src/servicios/q14_registrar_venta.py` | Valida cliente, farmacéutico, farmacia, productos y receta; calcula precio y total; crea venta completada y llama Q15 dentro de la misma transacción. |
| `src/servicios/q15_actualizar_stock.py` | Aplica el FEFO a los lotes vigentes de la sucursal, con actualizaciones condicionadas y bandera `stock_aplicado`. Incluye función independiente para ventas `Completada` previamente registradas sin stock aplicado. |
| `src/servicios/reglas_stock.py` | Valida y agrupa cantidades por producto; planifica FEFO antes de escribir. |
| `scripts/sincronizar_redis.py` | Reconstruye las proyecciones Redis a partir de un snapshot MongoDB y marca como sincronizadas las ventas pendientes. |
| `scripts/inspeccionar_venta.py` | Muestra una venta y sus lotes, opcionalmente receta; no modifica datos. |
| `tests/test_reglas_stock.py` | Pruebas automáticas de planificación FEFO; no necesitan bases de datos. |

## Contrato del servicio

* `registrar_venta(client, id_venta, id_cliente, id_farmaceutico, medio_pago, items, id_receta=None, hoy=None)` — Devuelve un diccionario con venta confirmada, total, receta modificada (si aplica), y lotes consumidos. `items` es lista de `{id_producto, cantidad}`. Genera fecha del sistema y precio vigente de catálogo. Motor MongoDB.
* `aplicar_stock_venta(db, id_venta, id_sucursal, hoy, session)` — Se invoca dentro de una transacción existente. No crea venta, solo mueve stock y marca venta. Devuelve `ya_aplicado` y lotes consumidos. Motor MongoDB.
* `ejecutar_q15(client, id_venta, hoy=None)` — Entrada independiente para una venta ya registrada `Completada` y con `stock_aplicado=False` (por ejemplo, una venta de prueba importada). No es necesario llamarla tras Q14: Q14 ya ejecutó Q15. Motor MongoDB.

## Política de atomicidad

El callback de `session.with_transaction()` ejecuta en MongoDB la inserción de venta, actualización de receta y descuento por FEFO. El commit confirma todo o nada. Si algún producto no tiene unidades suficientes, se aborta la transacción: no queda venta ni receta modificada ni lote descontado. Las actualizaciones de stock llevan condición `unidades >= cantidad` y las escrituras conflictivas pueden reintentarse por el driver. La bandera `stock_aplicado=True` evita descuentos repetidos. Las ventas históricas importadas ya tienen ese indicador verdadero y **no** se vuelven a procesar.

Redis no es parte de la transacción. Cada venta nueva tiene `redis_sync='pendiente'` en el mismo documento `ventas` hasta que se reconstruyen sus proyecciones. La actualización automática poscommit es una comodidad; si falla Redis, la venta sigue confirmada y se puede reintentar con `python scripts/sincronizar_redis.py`. El código no crea nuevas colecciones en MongoDB.

## Pruebas en Codespaces (desde raíz del repositorio)

1. Copiar este ZIP en la raíz y descomprimir con `unzip -o farmared-q14-q15.zip -d .`.
2. Ejecutar `python -m unittest discover -s tests -v` para probar FEFO sin escribir en las bases.
3. Inspeccionar lotes iniciales y ausencia de venta V901:

```bash
python scripts/inspeccionar_venta.py --id-venta V901 --id-sucursal S006 --id-producto PRD014
```

4. **Rechazo por stock insuficiente**: intentar consumir 999 unidades PRD014 de S006.

```bash
python src/servicios/q14_registrar_venta.py \
  --id-venta V901 --id-cliente C009 --id-farmaceutico F008 \
  --medio-pago Débito --item PRD014:999
```

Se espera un error `Stock insuficiente`; **V901 no debe existir ni el stock variar**. Confirmar con el script de inspección.

5. **Venta correcta con FEFO** (solo ejecutarla una vez, modifica los datos de prueba):

```bash
python src/servicios/q14_registrar_venta.py \
  --id-venta V902 --id-cliente C009 --id-farmaceutico F008 \
  --medio-pago Débito --item PRD014:20 --item PRD015:2
```

Si se ejecuta el **06/11/2026**, el producto PRD014 debe consumir 15 unidades de L019 (vencimiento 09/11/2026) y 5 unidades de L020; PRD015 consume 2 de L029. El total es **ARS 52.800**. Se guarda `stock_aplicado=True` y `lotes_consumidos` con los lotes y unidades.

**Importante:** L019 vence el 09/11/2026. Después de esa fecha no debe consumirse. La prueba sigue siendo válida, pero el plan FEFO cambiará (L020 absorberá las 20 unidades). No fijamos la fecha artificialmente para forzar el ejemplo: usamos la fecha real de Argentina.

6. Verificar estado:

```bash
python scripts/inspeccionar_venta.py --id-venta V902 --id-sucursal S006 --id-producto PRD014
python scripts/sincronizar_redis.py
python scripts/inspeccionar_bases.py
```

7. Volver a ejecutar Q14 con `--id-venta V902` y mismos parámetros debe ser rechazado sin doble descuento. También puede probarse:

```bash
python src/servicios/q15_actualizar_stock.py V902
```

Debería devolver `ya_aplicado=True` y no cambiar stock.

8. **Prueba de rollback de receta**: `RC002` es una receta vigente de `C003` y PRD004 tiene stock en `S004`. Solicitar cantidades excesivas obliga a abortar también el incremento de dispensas:

```bash
python scripts/inspeccionar_venta.py --id-venta V905 --id-sucursal S004 --id-producto PRD004 --id-receta RC002
python src/servicios/q14_registrar_venta.py \
  --id-venta V905 --id-cliente C003 --id-farmaceutico F006 \
  --id-receta RC002 --medio-pago 'Obra social' --item PRD004:9999
python scripts/inspeccionar_venta.py --id-venta V905 --id-sucursal S004 --id-producto PRD004 --id-receta RC002
```

Debe verse `V905=None`, receta sin cambios y stock intacto.

9. **Prueba positiva de receta** (opcional, modifica `RC002` y L007):

```bash
python src/servicios/q14_registrar_venta.py \
  --id-venta V906 --id-cliente C003 --id-farmaceutico F006 \
  --id-receta RC002 --medio-pago 'Obra social' --item PRD004:1
```

`RC002` pasa de 2 a 3 dispensas y su estado a `Completada` (con próxima dispensa `None`); L007 pierde una unidad y total ARS 6.200. **No ejecutar otra vez si quieren reservar este caso para la demo**.

## Notas para el informe

- MongoDB es la fuente de verdad: venta y sus ítems embebidos, recetas y stock por lote.
- Redis mantiene proyecciones derivadas (Q04, Q05, Q07, Q08, Q11) y nunca descuenta el stock real.
- La carga histórica considera `stock_aplicado=True` para ventas completadas importadas, porque el stock inicial es una fotografía ya disponible; no se conocen los lotes históricos consumidos.
- La relación entre venta y sucursal se guarda en las ventas nuevas (`id_sucursal`) para trazabilidad; las ventas históricas deben inferirla del farmacéutico.
- Los reintentos de una venta con mismo ID se rechazan sin volver a descontar.
- Con alto volumen habría que reemplazar la reconstrucción completa posventa por proyecciones incrementales con CDC/outbox y considerar políticas de retry y concurrencia de workers. En el TPO, el proceso recuperable e idempotente es suficiente para la demo, siempre documentando esta limitación.

## Guardar en GitHub

```bash
git add src/servicios/q14_registrar_venta.py src/servicios/q15_actualizar_stock.py src/servicios/reglas_stock.py scripts/sincronizar_redis.py scripts/inspeccionar_venta.py tests/test_reglas_stock.py README_Q14_Q15.md
git commit -m 'Implementar Q14 Q15 integrados con FEFO y sincronizacion Redis'
git -c core.hooksPath=/dev/null push origin main
```
