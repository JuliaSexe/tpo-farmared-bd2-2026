# Q04 y Q05 usando Redis — FarmaRed

Este paquete **actualiza** tres archivos ya existentes sin cambiar los CSV ni las colecciones de MongoDB.

| Archivo | Responsabilidad |
|---|---|
| `scripts/construir_redis.py` | Reconstruye proyecciones de stock, vencimientos, ranking e ingresos, e incorpora Q04 y Q05. |
| `src/consultas/q04_clientes_multiples_recetas.py` | Lee el `Hash` de Redis y obtiene nombres de MongoDB. |
| `src/consultas/q05_ventas_farmaceuticos.py` | Lee farmacéuticos activos de MongoDB y usa `ZCOUNT` en Redis, con ventana móvil de 60 días. |

## Estructuras nuevas

* `farmared:recetas:conteo_por_cliente` — Hash: `id_cliente -> cantidad de recetas`, incluye todos los estados.
* `farmared:ventas:farmaceutico:<id>` — Sorted Set: `id_venta -> fecha de la venta (score UTC)`, solo estados distintos de `Anulada`.
* `farmared:meta:reconstruccion` — Marca de existencia e información de cuándo fue ejecutado el proceso; **no garantiza frescura**.

Las estructuras anteriores de Q07/Q08/Q11 se mantienen. Redis **no** almacena el stock real ni confirma ventas.

## Instalación y prueba

Desde la raíz del repositorio en Codespaces:

```bash
unzip -o farmared-q04-q05-redis.zip -d .
python scripts/construir_redis.py
python src/consultas/q04_clientes_multiples_recetas.py
python src/consultas/q05_ventas_farmaceuticos.py
```

Para los CSV actuales, al 2026-11-06 se esperan **4 clientes** en Q04, y **15 farmacéuticos activos, 18 ventas no anuladas y 3 con cero** en Q05. Los resultados de Q05 cambiarán según la fecha real de ejecución.

## Limitaciones y escalabilidad

* Es una **reconstrucción manual**. Si se modifica una receta o venta, Redis puede quedar desactualizado hasta reconstruirse. Esta versión no debe reconstruirse al mismo tiempo que hay escrituras concurrentes sobre MongoDB.
* En una versión de producción convendría sincronizar cambios confirmados con una cola/outbox, reintentos idempotentes y supervisar el retraso de sincronización.
* Un Sorted Set de todas las ventas por farmacéutico crece con el historial. Para escalar, puede particionarse por mes o conservar únicamente datos de la ventana de consulta más un margen, mediante mantenimiento periódico.
* El índice Q05 incluye ventas pendientes, excluye anuladas y utiliza la fecha de calendario original de los CSV.
* El beneficio esperado en escala es evitar agregaciones repetidas sobre millones de ventas y recetas. No se ha realizado una prueba de rendimiento que permita afirmar que Redis es más rápido con los datos actuales.

## Prueba cruzada con MongoDB

Después de reconstruir Redis, ejecutar:

```bash
python scripts/validar_agregaciones_redis.py
```

Esta prueba **no escribe**; recalcula Q04 y Q05 en MongoDB y comprueba que sus resultados sean iguales a los de Redis. Si hay diferencias, falla con un mensaje para revisar la sincronización.
