# Auditoría de FarmaRed — 06/11/2026

## Confirmado al revisar el repositorio

1. Están versionados los módulos Q01–Q15.
2. Los nueve CSV originales y nueve adicionales están versionados.
3. MongoDB funciona como fuente de verdad y se preparó con replica set rs0. Redis utiliza AOF.
4. Los scripts de carga hacen inserciones idempotentes con `$setOnInsert`, sin borrar ni resetear datos existentes.
5. Q14 y Q15 comparten una transacción, con FEFO y marca `stock_aplicado`.
6. `scripts/sincronizar_redis.py` puede volver a intentar la publicación de proyecciones tras una venta confirmada.

## Corregido en este paquete

- `README.md` estaba desactualizado: decía que no existían colecciones ni consultas, y mostraba el ZIP inicial como requisito permanente. Se reemplaza por instrucciones de carga y uso reales.
- Nuevo `scripts/auditar_tpo.py` de **solo lectura**: verifica cobertura de CSV, colecciones, índices, Q04, Q05, Q07, Q08 y Q11 comparando Redis con MongoDB. Esta ampliación permite detectar proyecciones desactualizadas.

## Pendientes de verificar en el Codespace del grupo

- Ejecutar el flujo de arranque desde **un Codespace nuevo**, no desde la instancia que ya tiene pruebas insertadas.
- Correr la nueva auditoría y confirmar todas las líneas `OK`.
- Probar escenarios de validación adicionales: producto inactivo, cliente inactivo, receta de otro cliente, farmacia no habilitada y venta duplicada. No alcanza con las cuatro pruebas unitarias de FEFO.
- Para una defensa robusta, añadir un test de integración automatizado de rollback/concurrencia (los casos se probaron manualmente en el Codespace).
- Medir tiempo de ejecución con volúmenes grandes antes de afirmar una mejora cuantitativa de rendimiento.

## Limitaciones a documentar expresamente

- **Sin transacción distribuida**: Mongo confirma antes de actualizar Redis.
- **Reconstrucción completa posventa**: hoy Redis se recalcula desde todos los documentos; no es actualización incremental.
- **Sin reset idempotente del estado de demo**: volver a cargar los CSV no revierte cambios de ventas o recetas ya procesadas.
- **Crecimiento de Sorted Sets** de Q05: la ventana se mueve al consultar, pero los miembros antiguos no se eliminan automáticamente.
- **Q11 al cambiar de mes**: la clave del mes nuevo puede no existir hasta reconstruir Redis. Conviene ejecutar `python scripts/construir_redis.py` al iniciar el mes, o implementar una lectura explícita de ceros si no hubo ventas aún. No usar el valor del mes anterior.
- **Reconstrucción concurrente**: `construir_redis.py` manual no comparte el lock del sincronizador; no ejecutar simultáneamente con escrituras.
- **Baja lógica y datos históricos**: no alterar las ventas históricas cuando se modifica un cliente o farmacéutico.

**Alcance de esta revisión:** inspección estática del repositorio GitHub y evidencia de las capturas de pruebas realizadas por el equipo. No se ejecutaron integraciones en un Codespace nuevo desde esta sesión.
