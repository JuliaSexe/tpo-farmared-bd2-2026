# Ajuste puntual de Q14 — receta opcional para productos de venta libre

En el repositorio revisado (15/11/2026), `src/servicios/q14_registrar_venta.py` rechaza un `id_receta` cuando la venta contiene solamente productos con `condicion_venta='Venta libre'`. El enunciado exige receta para productos bajo receta, pero no prohíbe que un cliente presente una receta adicional para un producto de venta libre.

El script adjunto reemplaza **solo ese bloque** por una validación de existencia y pertenencia al cliente. Mantiene `tipo='Venta libre'`, conserva `id_receta` como referencia informativa y **no actualiza dispensas**. Si el ID opcional no existe o pertenece a otro cliente, se rechaza la referencia para evitar datos huérfanos.

Desde la raíz del repositorio en Codespaces:

```bash
python scripts/aplicar_ajuste_receta_libre.py
python scripts/probar_receta_opcional.py
python -m unittest discover -s tests -v
```

Si la prueba termina bien, guardar la modificación de `src/servicios/q14_registrar_venta.py` y los scripts de prueba. Los archivos originales y las consultas Q01–Q13 no se alteran. La prueba usa una base temporal y no toca la base `farmared` ni Redis.
