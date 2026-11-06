# FarmaRed — Menú de terminal para la demo

## Para abrir

Desde la **terminal de Codespaces**, en la raíz del repositorio:

```bash
python menu.py
```

El menú tiene tres secciones:

- **Consultas Q01–Q12**: lectura y agregaciones. Q03 solicita un ID de cliente; Q10 solicita el ID de sucursal. Las demás se ejecutan sin parámetros adicionales.
- **Servicios Q13–Q15**: Q13 permite alta, modificación y baja lógica de clientes; Q14 registra una venta completada llamando internamente a Q15 (FEFO); Q15 se usa en forma independiente solo para ventas completadas cuya marca `stock_aplicado` todavía esté en `False`.
- **Herramientas**: inspección de las bases, verificación del entorno, auditoría de MongoDB/Redis, pruebas unitarias FEFO, sincronización de proyecciones, inspección de venta/receta/lotes y carga idempotente de archivos CSV.

## Características y precauciones

- **No reemplaza** los scripts individuales: los ejecuta con Python, muestra su salida real y permite volver al menú.
- Funciona en la terminal del Codespace ya configurado; no requiere instalar librerías nuevas ni levantar otro servidor.
- Para todas las operaciones con escritura pide escribir `CONFIRMAR`. **Las ventas exitosas descuentan stock y modifican la base**, por lo que no uses los IDs V902/V906, ya registrados en el entorno actual.
- La sincronización de Redis ocurre luego de una venta Q14 confirmada y también se puede ejecutar desde Herramientas. Redis sigue siendo una proyección reconstruible de MongoDB.
- El menú de carga **no limpia** las bases ni restaura los valores previos de stock, recetas o ventas; solo inserta documentos CSV faltantes. Para una demo reproducible, prepará un Codespace nuevo con el procedimiento del README principal.
- Si una consulta muestra datos antiguos de Redis, usá primero Herramientas → sincronizar o reconstruir, y ejecutá la auditoría para verificar consistencia.
- Para salir, regresá con `0`. Al salir del menú, MongoDB y Redis continúan funcionando.

## Ejemplo de navegación sin escribir nada

```text
$ python menu.py

FARMARED | TPO BASE DE DATOS II
  1. Consultas Q01 a Q12 (lectura)
  2. Servicios Q13 a Q15 (escritura)
  3. Verificaciones y administración
  0. Salir

Seleccioná una sección: 1
Elegí una consulta (0-12): 7

Q07 — Top 5 productos vendidos
Motor: MongoDB + Redis
...
Presioná Enter para volver al menú...
```

## Archivos agregados por este paquete

- `menu.py`: interfaz interactiva, sin lógica duplicada.
- `scripts/auditar_tpo.py`: auditoría de solo lectura de las bases y proyecciones Q04/Q05/Q07/Q08/Q11.
- `README.md`: documentación general actualizada.
- `RESULTADOS_REVISION.md`: revisión de reproducibilidad y limitaciones.
- `README_MENU.md`: esta guía.
