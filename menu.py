"""Interfaz de terminal para las 15 funcionalidades del TPO FarmaRed.

Uso desde la raíz del proyecto: python menu.py
No almacena datos nuevos: ejecuta los scripts existentes del repositorio.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONSULTAS = {
    1: ("Productos y proveedores activos", "q01_productos_proveedores.py", "MongoDB"),
    2: ("Ventas pendientes", "q02_ventas_pendientes.py", "MongoDB"),
    3: ("Historial de un cliente", "q03_historial_cliente.py", "MongoDB"),
    4: ("Clientes con múltiples recetas", "q04_clientes_multiples_recetas.py", "MongoDB + Redis"),
    5: ("Ventas por farmacéutico (60 días)", "q05_ventas_farmaceuticos.py", "MongoDB + Redis"),
    6: ("Recetas con dispensa atrasada", "q06_recetas_atrasadas.py", "MongoDB"),
    7: ("Top 5 productos vendidos", "q07_productos_mas_vendidos.py", "MongoDB + Redis"),
    8: ("Lotes con menos de 50 unidades", "q08_lotes_stock_bajo.py", "MongoDB + Redis"),
    9: ("Ventas libres menores a $5.000", "q09_ventas_libres.py", "MongoDB"),
    10: ("Clientes atendidos por sucursal", "q10_clientes_por_sucursal.py", "MongoDB"),
    11: ("Ingresos mensuales por farmacéutico", "q11_ingresos_farmaceuticos.py", "MongoDB + Redis"),
    12: ("Clientes sin ventas en el último año", "q12_clientes_sin_ventas.py", "MongoDB"),
}


def titulo(texto: str) -> None:
    print("\n" + "=" * 64)
    print(f"  {texto}")
    print("=" * 64)


def elegir(mensaje: str, validas: set[str]) -> str:
    while True:
        opcion = input(f"\n{mensaje}: ").strip()
        if opcion in validas:
            return opcion
        print("Opción no válida; volvé a intentar.")


def pedir(campo: str, obligatorio: bool = True) -> str:
    while True:
        valor = input(f"  {campo}{'' if obligatorio else ' (opcional)'}: ").strip()
        if valor or not obligatorio:
            return valor
        print("  Este dato es obligatorio.")


def confirmar(descripcion: str) -> bool:
    print("\nATENCIÓN: esta opción puede modificar los datos de FarmaRed.")
    print(descripcion)
    return input("Escribí CONFIRMAR para continuar (otra cosa cancela): ").strip() == "CONFIRMAR"


def ejecutar(ruta: str, *args: str) -> bool:
    if ruta == "-m":
        comando = [sys.executable, "-m", *args]
    else:
        archivo = RAIZ / ruta
        if not archivo.is_file():
            print(f"\nERROR: no existe {ruta}. Revisá que el ZIP se extrajo en la raíz.")
            return False
        comando = [sys.executable, str(archivo), *args]
    print("\n" + "-" * 64)
    print("Ejecutando:", shlex.join(["python", ruta, *args]))
    print("-" * 64, flush=True)
    try:
        r = subprocess.run(comando, cwd=RAIZ, check=False)
    except OSError as exc:
        print(f"No se pudo iniciar el proceso: {exc}")
        return False
    print("-" * 64)
    if r.returncode == 0:
        print("Ejecución finalizada correctamente.")
        return True
    print(f"La operación terminó con código {r.returncode}. Revisá el mensaje anterior.")
    return False


def pausar() -> None:
    input("\nPresioná Enter para volver al menú...")


def consultas() -> None:
    while True:
        titulo("CONSULTAS — lectura y agregaciones")
        for n, (nombre, _, motor) in CONSULTAS.items():
            print(f" {n:>2}. {nombre:<40} [{motor}]")
        print("  0. Volver al menú principal")
        opcion = elegir("Elegí una consulta (0-12)", {str(i) for i in range(13)})
        if opcion == "0":
            return
        numero = int(opcion)
        nombre, archivo, motor = CONSULTAS[numero]
        titulo(f"Q{numero:02d} — {nombre}")
        print("Motor:", motor)
        argumentos = []
        if numero == 3:
            argumentos.append(pedir("ID cliente (ejemplo C001)"))
        elif numero == 10:
            argumentos.append(pedir("ID sucursal (ejemplo S002)"))
        ejecutar(f"src/consultas/{archivo}", *argumentos)
        pausar()


def alta_cliente() -> None:
    titulo("Q13 — Alta de cliente")
    print("Se validará que no exista el ID ni el DNI.")
    campos = [
        ("id-cliente", "ID cliente"), ("nombre", "Nombre"),
        ("apellido", "Apellido"), ("dni", "DNI"),
        ("email", "Email"), ("telefono", "Teléfono"),
        ("ciudad", "Ciudad"), ("provincia", "Provincia"),
        ("obra-social", "Obra social"),
    ]
    args = ["alta"]
    for opcion, label in campos:
        args.extend(["--" + opcion, pedir(label)])
    nro = pedir("Número de afiliado", obligatorio=False)
    if nro:
        args.extend(["--nro-afiliado", nro])
    if confirmar("Se creará un cliente nuevo en MongoDB."):
        ejecutar("src/servicios/q13_abm_clientes.py", *args)
    else:
        print("Alta cancelada.")


def modificar_cliente() -> None:
    titulo("Q13 — Modificar cliente")
    cliente = pedir("ID cliente a modificar")
    print("Dejá en blanco los campos que no quieras cambiar.")
    print("Para borrar el número de afiliado, escribí un guion (-).")
    campos = [
        ("email", "Email"), ("telefono", "Teléfono"),
        ("ciudad", "Ciudad"), ("provincia", "Provincia"),
        ("obra-social", "Obra social"), ("nro-afiliado", "Número de afiliado"),
    ]
    args = ["modificar", "--id-cliente", cliente]
    cambio = False
    for opcion, label in campos:
        valor = pedir(label, obligatorio=False)
        if valor:
            args.extend(["--" + opcion, "" if opcion == "nro-afiliado" and valor == "-" else valor])
            cambio = True
    if not cambio:
        print("No ingresaste cambios. Se canceló la operación.")
    elif confirmar("Se modificarán exclusivamente los campos indicados del cliente."):
        ejecutar("src/servicios/q13_abm_clientes.py", *args)
    else:
        print("Modificación cancelada.")


def baja_cliente() -> None:
    titulo("Q13 — Baja lógica de cliente")
    cliente = pedir("ID cliente")
    if confirmar(f"El cliente {cliente} conservará su historial y quedará activo=False."):
        ejecutar("src/servicios/q13_abm_clientes.py", "baja", "--id-cliente", cliente)
    else:
        print("Baja cancelada.")


def items_venta() -> list[str]:
    print("Ingresá los ítems separados por comas, por ejemplo: PRD014:2,PRD015:1")
    while True:
        texto = pedir("Productos y cantidades")
        valores = [x.strip() for x in texto.split(",")]
        ok = bool(valores) and all(
            re.fullmatch(r"[^\s:,]+:[1-9][0-9]*", v) for v in valores
        )
        if ok:
            resultado = []
            for v in valores:
                resultado.extend(["--item", v])
            return resultado
        print("Formato inválido. Usá ID:cantidad positiva, separado por comas.")


def registrar_venta() -> None:
    titulo("Q14 — Registrar venta completada (Q15 aplica FEFO)")
    print("Una venta exitosa DESCUENTA stock real y puede modificar la receta.")
    print("No usar identificadores ya existentes; la operación los rechazará.")
    id_venta = pedir("ID venta nueva (ejemplo V950)")
    id_cliente = pedir("ID cliente activo")
    id_farmaceutico = pedir("ID farmacéutico activo")
    receta = pedir("ID receta", obligatorio=False)
    medios = ["Efectivo", "Débito", "Crédito", "Transferencia", "Obra social"]
    print("\nMedios de pago:")
    for i, m in enumerate(medios, 1):
        print(f"  {i}. {m}")
    medio = medios[int(elegir("Medio de pago", {str(i) for i in range(1, 6)})) - 1]
    items = items_venta()
    args = ["--id-venta", id_venta, "--id-cliente", id_cliente,
            "--id-farmaceutico", id_farmaceutico, "--medio-pago", medio]
    if receta:
        args.extend(["--id-receta", receta])
    args.extend(items)
    print("\nResumen de solicitud")
    print(f"  Venta: {id_venta} | Cliente: {id_cliente} | Farmacéutico: {id_farmaceutico}")
    print(f"  Medio: {medio} | Receta: {receta or 'ninguna'}")
    print("  Ítems:", ", ".join(items[1::2]))
    if confirmar("Se registrará la venta, se aplicará FEFO y se sincronizará Redis tras el commit."):
        ejecutar("src/servicios/q14_registrar_venta.py", *args)
    else:
        print("Registro cancelado.")


def actualizar_stock() -> None:
    titulo("Q15 — Aplicar stock de una venta ya registrada")
    print("Normalmente NO se usa después de Q14: Q14 ya aplica Q15.")
    print("Solo corresponde a ventas Completada con stock_aplicado=False.")
    venta = pedir("ID venta")
    if confirmar(f"Se verificará y, si corresponde, descontará el stock de {venta}."):
        if ejecutar("src/servicios/q15_actualizar_stock.py", venta):
            print("\nVerificando si quedaron proyecciones pendientes para Redis...")
            ejecutar("scripts/sincronizar_redis.py")
    else:
        print("Operación cancelada.")


def servicios() -> None:
    acciones = {
        "1": ("Q13: Alta de cliente", alta_cliente),
        "2": ("Q13: Modificación de cliente", modificar_cliente),
        "3": ("Q13: Baja lógica de cliente", baja_cliente),
        "4": ("Q14: Registrar venta (incluye Q15/FEFO)", registrar_venta),
        "5": ("Q15: Aplicar stock a una venta existente", actualizar_stock),
    }
    while True:
        titulo("SERVICIOS — operaciones con escritura")
        for n, (nombre, _) in acciones.items():
            print(f"  {n}. {nombre}")
        print("  0. Volver al menú principal")
        eleccion = elegir("Elegí una operación", {"0", *acciones})
        if eleccion == "0":
            return
        acciones[eleccion][1]()
        pausar()


def inspeccionar_venta() -> None:
    titulo("Inspeccionar venta, lote y receta (solo lectura)")
    venta = pedir("ID venta")
    sucursal = pedir("ID sucursal")
    producto = pedir("ID producto")
    receta = pedir("ID receta", obligatorio=False)
    args = ["--id-venta", venta, "--id-sucursal", sucursal, "--id-producto", producto]
    if receta:
        args.extend(["--id-receta", receta])
    ejecutar("scripts/inspeccionar_venta.py", *args)


def preparar_datos() -> None:
    titulo("Cargar CSV iniciales (idempotente por inserción)")
    print("No borra bases ni restaura saldos alterados por pruebas anteriores.")
    print("Solo incorpora documentos faltantes y reconstruye proyecciones de Redis.")
    if not confirmar("Se ejecutarán cargar_originales, cargar_adicionales y construir_redis."):
        print("Carga cancelada.")
        return
    for archivo in ("cargar_originales.py", "cargar_adicionales.py", "construir_redis.py"):
        if not ejecutar("scripts/" + archivo):
            print("La secuencia se interrumpió. Revisá el error antes de continuar.")
            return


def herramientas() -> None:
    acciones = {
        "1": ("Estado de bases (colecciones y claves)", lambda: ejecutar("scripts/inspeccionar_bases.py")),
        "2": ("Verificar entorno MongoDB y Redis", lambda: ejecutar("scripts/verificar_entorno.py")),
        "3": ("Auditoría completa (solo lectura)", lambda: ejecutar("scripts/auditar_tpo.py")),
        "4": ("Validar Q04 y Q05 contra MongoDB", lambda: ejecutar("scripts/validar_agregaciones_redis.py")),
        "5": ("Pruebas FEFO (sin modificar datos)", lambda: ejecutar("-m", "unittest", "discover", "-s", "tests", "-v")),
        "6": ("Sincronizar pendientes hacia Redis", lambda: ejecutar("scripts/sincronizar_redis.py")),
        "7": ("Reconstruir índices y agregaciones Redis", lambda: reconstruir_redis()),
        "8": ("Inspeccionar venta, receta y lotes", inspeccionar_venta),
        "9": ("Cargar originales y adicionales si faltan", preparar_datos),
    }
    while True:
        titulo("HERRAMIENTAS — mantenimiento y verificación")
        for n, (nombre, _) in acciones.items():
            print(f"  {n}. {nombre}")
        print("  0. Volver al menú principal")
        opcion = elegir("Elegí una herramienta", {"0", *acciones})
        if opcion == "0":
            return
        acciones[opcion][1]()
        pausar()


def reconstruir_redis() -> None:
    print("No modifica MongoDB. Reemplaza las proyecciones Redis con los datos actuales.")
    print("No ejecutar mientras se registran ventas simultáneamente.")
    if confirmar("Se reconstruirán todas las claves de proyección de FarmaRed."):
        ejecutar("scripts/construir_redis.py")
    else:
        print("Reconstrucción cancelada.")


def main() -> None:
    if not (RAIZ / "src" / "consultas").is_dir():
        print("ERROR: colocá menu.py en la carpeta raíz de tpo-farmared-bd2-2026.")
        return
    while True:
        titulo("FARMARED | TPO BASE DE DATOS II")
        print("  1. Consultas Q01 a Q12 (lectura)")
        print("  2. Servicios Q13 a Q15 (escritura)")
        print("  3. Verificaciones y administración")
        print("  0. Salir")
        opcion = elegir("Seleccioná una sección", {"0", "1", "2", "3"})
        if opcion == "0":
            print("Hasta luego. No se detienen los motores de base de datos.")
            return
        {"1": consultas, "2": servicios, "3": herramientas}[opcion]()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nMenú cerrado. No se ejecutó ningún comando adicional.")
