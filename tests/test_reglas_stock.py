"""Pruebas sin MongoDB de la lógica de planificación FEFO.

Ejecutar: python -m unittest discover -s tests -v
"""
import unittest
from datetime import datetime

from src.servicios.reglas_stock import (
    ReglaNegocioError, planificar_consumo_fefo
)


def lote(id, unidades, fecha):
    return {"_id":id,"unidades":unidades,"vencimiento":datetime.fromisoformat(fecha)}


class TestFEFO(unittest.TestCase):
    def test_consumo_en_dos_lotes(self):
        plan=planificar_consumo_fefo(
            [{"id_producto":"PRD014","cantidad":20}],
            {"PRD014":[lote("L020",90,"2027-09-30"),lote("L019",15,"2026-11-09")]}
        )
        self.assertEqual(plan, [
            {"id_lote":"L019","id_producto":"PRD014","cantidad":15},
            {"id_lote":"L020","id_producto":"PRD014","cantidad":5},
        ])

    def test_stock_insuficiente_rechaza_sin_plan(self):
        with self.assertRaises(ReglaNegocioError):
            planificar_consumo_fefo(
                [{"id_producto":"PRD014","cantidad":106}],
                {"PRD014":[lote("L019",15,"2026-11-09"),lote("L020",90,"2027-09-30")]}
            )

    def test_productos_repetidos_se_suman(self):
        plan=planificar_consumo_fefo(
            [{"id_producto":"PRD014","cantidad":9},
             {"id_producto":"PRD014","cantidad":11}],
            {"PRD014":[lote("L019",15,"2026-11-09"),lote("L020",90,"2027-09-30")]}
        )
        self.assertEqual(sum(x["cantidad"] for x in plan),20)
        self.assertEqual(len(plan),2)

    def test_unidades_no_positivas_se_rechazan(self):
        with self.assertRaises(ReglaNegocioError):
            planificar_consumo_fefo([{"id_producto":"PRD014","cantidad":0}],{})

if __name__ == "__main__":
    unittest.main()
