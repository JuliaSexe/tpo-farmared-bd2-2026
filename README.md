# TPO Base de Datos II 2026-2 — FarmaRed

Proyecto inicial para desarrollar el TPO de FarmaRed S.A. en **GitHub Codespaces** con dos paradigmas NoSQL:

- **MongoDB** (documentos): almacén principal, incluidas ventas, recetas y stock.
- **Redis** (clave-valor): reportes agregados persistidos mediante AOF.
- **Python**: implementación futura de las consultas q01–q15.

> Estado: entorno y datasets originales preparados. **Las bases todavía no contienen los CSV y las 15 consultas NO están implementadas.** La carga idempotente y los registros adicionales se desarrollarán en los siguientes pasos.

## Cómo comenzar en Codespaces

1. Crear un repositorio privado en GitHub, con README inicial.
2. Desde el repositorio, seleccionar **Code > Codespaces > Create codespace on main**.
3. Subir el ZIP inicial al explorador de archivos de Codespaces.
4. En la terminal del Codespace ejecutar `unzip -o tpo-farmared-inicio.zip -d .` y luego `rm tpo-farmared-inicio.zip`.
5. Abrir paleta de comandos con `Ctrl+Shift+P` y ejecutar **Codespaces: Rebuild Container**.
6. Al reconstruir, se inicia el entorno Docker Compose y se ejecutan automáticamente los scripts `scripts/inicializar_mongo.py` y `scripts/verificar_entorno.py`.
7. Verificar manualmente, si se desea, ejecutando `python scripts/verificar_entorno.py`.
8. Guardar en GitHub: `git add .`, `git commit -m "Configurar MongoDB y Redis en Codespaces"`, `git push`.

Si Codespaces informa un error al reconstruir, abrir el **creation log**. No borrar los volúmenes de datos.

## Estructura

```text
.devcontainer/
  devcontainer.json       Configuración del Codespace
  Dockerfile              Python y librerías

data/
  originales/             Los 9 CSV entregados por la cátedra
  adicionales/            Registros nuevos (pendiente)

scripts/
  inicializar_mongo.py    Inicia rs0 sin duplicar configuración
  verificar_entorno.py    Verifica MongoDB y Redis
  inspeccionar_bases.py   Muestra cantidades almacenadas

src/
  consultas/              q01–q12 (pendientes)
  servicios/              q13–q15 (pendientes)

docker-compose.yml        MongoDB, Redis y aplicación
requirements.txt          Librerías Python
```

## Comprobación esperada

En la terminal **del contenedor de desarrollo**:

```bash
python scripts/verificar_entorno.py
```

Salida prevista, una vez que los servicios estén en ejecución:

```text
OK: MongoDB accesible y replica set rs0 activo.
OK: Redis accesible y persistencia AOF habilitada.
Entorno listo. Siguiente etapa: carga de datos desde CSV.
```

Para inspeccionar el estado de ambas bases:

```bash
python scripts/inspeccionar_bases.py
```

Al principio no habrá colecciones ni datos cargados: eso es normal. Los archivos CSV disponibles en `data/originales/` no se importan automáticamente.

## Decisiones técnicas preliminares

- MongoDB arranca como **replica set de un solo nodo**, necesario para usar transacciones multidocumento. En producción se requiere una configuración de mayor disponibilidad y seguridad.
- Redis tiene **AOF activado** (`appendfsync everysec`). Su información será derivada y reconstruible; nunca será la autoridad para decidir stock o confirmar ventas.
- Los servicios no exponen puertos al exterior de Codespaces. Python accede por nombres internos de servicio (`mongo` y `redis`).
- Los volúmenes de Docker conservan datos entre reinicios normales del Codespace, pero no sustituyen backups ni garantizan retención después de eliminarlo.
- Esta configuración es **para desarrollo académico** y no incluye autenticación de motores. No publicar los servicios ni usarlos con datos reales.

## Requisitos pendientes según la cátedra

- Carga reproducible e idempotente de los 9 CSV.
- Incorporar >=10 registros propios por colección/tabla y justificar los casos de prueba.
- Implementar y documentar q01–q15, incluidas verificaciones y estados antes/después.
- Resolver integridad y transacciones q14/q15 (FEFO, recetas, ventas y stock).
- Informe PDF, pruebas y demo en vivo.
