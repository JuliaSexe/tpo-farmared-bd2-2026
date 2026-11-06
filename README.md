# FarmaRed — TPO Base de Datos II — 2.º cuatrimestre 2026

Implementación de una arquitectura de persistencia políglota sobre **MongoDB** (documentos) y **Redis** (clave-valor), desarrollada en Python y preparada para **GitHub Codespaces**.

## Arquitectura

| Componente | Responsabilidad |
|---|---|
| MongoDB 7.0 (`rs0`) | Fuente de verdad: clientes, sucursales, farmacéuticos, proveedores, productos, stock por lote, recetas y ventas con ítems embebidos. Transacciones de escritura Q14/Q15. |
| Redis 7.4 (AOF) | Proyecciones reconstruibles: conteos Q04, ventana temporal Q05, ranking Q07, índices de stock Q08, ingresos mensuales Q11. **No descuenta stock real ni confirma ventas.** |
| Python | Consultas, reglas de negocio, transacciones y coordinación de ambos motores. |

### Modelo de MongoDB

Se usan ocho colecciones: `clientes`, `sucursales`, `farmaceuticos`, `proveedores`, `productos`, `stock_lotes`, `recetas` y `ventas`. `detalle_ventas.csv` **no** crea una novena colección: los ítems se embeben en `ventas.items`. En todos los documentos, `_id` es el identificador de negocio (`C001`, `V001`, etc.). Los campos de referencia (`id_cliente`, `id_producto`, etc.) se validan en la aplicación; MongoDB no implementa claves foráneas.

### Estructuras Redis

| Clave o patrón | Tipo | Uso |
|---|---|---|
| `farmared:recetas:conteo_por_cliente` | Hash | Q04: número de recetas por cliente. |
| `farmared:ventas:farmaceutico:<id>` | Sorted Set | Q05: cada venta no anulada, con su fecha como score; se consulta con `ZCOUNT` usando los últimos 60 días calculados **al ejecutar**. |
| `farmared:ranking:productos:unidades` | Sorted Set | Q07: top 5 por unidades vendidas en ventas completadas. |
| `farmared:stock:por_unidades` | Sorted Set | Q08: lotes con menos de 50 unidades. |
| `farmared:stock:por_vencimiento` | Sorted Set | Índice secundario de vencimientos. |
| `farmared:ingresos:farmaceutico:AAAA-MM` | Hash | Q11: ingresos por farmacéutico y mes. |
| `farmared:meta:reconstruccion` | Hash | Metadatos de reconstrucción; no garantiza que Redis esté actualizado. |

## Preparación desde un Codespace NUEVO

1. Abrir este repositorio en GitHub y seleccionar **Code → Codespaces → Create codespace on main**.
2. Esperar a que termine la creación del entorno. `.devcontainer/devcontainer.json` y `docker-compose.yml` arrancan MongoDB, Redis y el contenedor Python. No hace falta instalar MongoDB, Redis ni Docker en Windows; tampoco ejecutar `docker compose` dentro de la terminal Python del Codespace.
3. Desde la **raíz del repositorio**, ejecutar en este orden:

```bash
python scripts/verificar_entorno.py
python scripts/cargar_originales.py
python scripts/cargar_adicionales.py
python scripts/construir_redis.py
python scripts/inspeccionar_bases.py
python -m unittest discover -s tests -v
python scripts/validar_agregaciones_redis.py
python scripts/auditar_tpo.py
```

Los scripts de carga son **idempotentes respecto de inserciones** (`$setOnInsert`): ejecutarlos nuevamente no duplica las filas ya importadas. Tampoco restablecen las modificaciones efectuadas por pruebas anteriores. La reconstrucción Redis reemplaza sus proyecciones desde el estado **actual** de MongoDB; no correrla mientras se hacen otras escrituras.

**Estado de demo:** si se utilizó previamente Q13/Q14/Q15, los conteos originales cambian (nuevos clientes, ventas, receta RC002 completada y stock descontado). No asumir que los resultados serán idénticos a los de una carga limpia; verificar con `scripts/auditar_tpo.py`.

## Interfaz interactiva de terminal

Para navegar por las **15 funcionalidades** sin recordar nombres de archivos:

```bash
python menu.py
```

Seleccioná **Consultas** (Q01–Q12), **Servicios** (Q13–Q15) o **Herramientas** (estado, pruebas y auditoría). El menú reutiliza los scripts existentes; no modifica la lógica de consultas ni reglas de negocio. **Toda escritura exige confirmación** y cambia datos reales de la base de prueba. Ver `README_MENU.md`.

## Consultas y servicios

| Nº | Módulo | Motor |
|---|---|---|
| Q01 | `src/consultas/q01_productos_proveedores.py` | MongoDB |
| Q02 | `src/consultas/q02_ventas_pendientes.py` | MongoDB |
| Q03 | `src/consultas/q03_historial_cliente.py` | MongoDB |
| Q04 | `src/consultas/q04_clientes_multiples_recetas.py` | Redis + MongoDB |
| Q05 | `src/consultas/q05_ventas_farmaceuticos.py` | Redis + MongoDB |
| Q06 | `src/consultas/q06_recetas_atrasadas.py` | MongoDB |
| Q07 | `src/consultas/q07_productos_mas_vendidos.py` | Redis + MongoDB |
| Q08 | `src/consultas/q08_lotes_stock_bajo.py` | Redis + MongoDB |
| Q09 | `src/consultas/q09_ventas_libres.py` | MongoDB |
| Q10 | `src/consultas/q10_clientes_por_sucursal.py` | MongoDB |
| Q11 | `src/consultas/q11_ingresos_farmaceuticos.py` | Redis + MongoDB |
| Q12 | `src/consultas/q12_clientes_sin_ventas.py` | MongoDB |
| Q13 | `src/servicios/q13_abm_clientes.py` | MongoDB |
| Q14 | `src/servicios/q14_registrar_venta.py` | MongoDB, luego Redis |
| Q15 | `src/servicios/q15_actualizar_stock.py` | MongoDB, luego Redis |

Cada script contiene una función principal para ser importada y, en general, también una interfaz CLI. Los comandos más útiles de demostración están aquí:

```bash
# Consultas parametrizadas
python src/consultas/q03_historial_cliente.py C001
python src/consultas/q10_clientes_por_sucursal.py S002

# Agregaciones e índices
python src/consultas/q04_clientes_multiples_recetas.py
python src/consultas/q05_ventas_farmaceuticos.py
python src/consultas/q07_productos_mas_vendidos.py
python src/consultas/q08_lotes_stock_bajo.py
python src/consultas/q11_ingresos_farmaceuticos.py

# Servicio ABM (consultar ayuda antes de modificar datos)
python src/servicios/q13_abm_clientes.py --help

# Registro transaccional de ventas, con aplicación de FEFO
python src/servicios/q14_registrar_venta.py --help
python src/servicios/q15_actualizar_stock.py --help
```

Para ejecutar Q01, Q02, Q06, Q09 y Q12 basta con `python` seguido de la ruta del módulo indicado en la tabla. Las consultas que dependen del tiempo usan fecha de Argentina en tiempo de ejecución, no una fecha fija.

## Consistencia e integridad

- El alta Q13 protege el DNI con índice `unique`, y las bajas son lógicas (`activo=False`).
- Q14 valida cliente activo, farmacéutico activo de una farmacia, productos activos y receta válida cuando se requiere; calcula el total según precios de catálogo y guarda los ítems.
- Q14 llama Q15 **dentro de la misma transacción MongoDB**: venta, dispensas y stock se confirman o revierten conjuntamente.
- Q15 aplica **FEFO** sobre lotes vigentes, condiciona cada decremento al stock disponible y evita aplicar dos veces el descuento (`stock_aplicado`). Las ventas históricas importadas figuran ya procesadas para no descontar nuevamente los saldos iniciales.
- Redis se sincroniza **después del commit**. Las ventas nuevas llevan `redis_sync='pendiente'` hasta la publicación de proyecciones. Si falla Redis, reintentar:

```bash
python scripts/sincronizar_redis.py
python scripts/auditar_tpo.py
```

**Limitación importante:** no existe una transacción distribuida MongoDB–Redis. Durante una falla o retraso, Redis puede quedar momentáneamente desactualizado. La sincronización actual reconstruye **todas** las proyecciones después de una venta nueva; es sencilla y recuperable para el TPO, pero no es incremental ni adecuada sin modificaciones para alto volumen. Para producción se evaluaría CDC/outbox, proyecciones incrementales, observabilidad y políticas de retención.

## Pruebas y demostración

```bash
# 4 pruebas unitarias de FEFO; no modifican las bases
python -m unittest discover -s tests -v

# Consistencia completa de proyecciones (solo lectura)
python scripts/auditar_tpo.py

# Inspección no destructiva de venta, receta y lotes
python scripts/inspeccionar_venta.py --id-venta V902 --id-sucursal S006 --id-producto PRD014
```

Las pruebas Q14/Q15 de rechazo por stock, rollback de receta, venta exitosa e idempotencia están documentadas en `README_Q14_Q15.md`. **Los ejemplos V902 y V906 ya se utilizaron en un Codespace de desarrollo; no volver a ejecutarlos esperando una inserción nueva.** En un entorno limpio pueden utilizarse una sola vez.

## Datasets y documentación complementaria

- `data/originales/`: nueve CSV provistos por la cátedra.
- `data/adicionales/`: nueve CSV con diez o más filas adicionales por archivo.
- `README_ADICIONALES.md`: decisiones sobre registros adicionales.
- `README_AGREGACIONES_REDIS.md`: Q04/Q05 y proyecciones materializadas.
- `README_Q14_Q15.md`: contratos, FEFO, transacciones y casos de prueba.

## Alcance

Entorno académico, con `rs0` de un nodo y motores sin autenticación ni exposición pública de puertos. Redis usa AOF (`everysec`), que no sustituye un backup. No usar con datos personales reales ni considerar este despliegue una configuración de producción.
