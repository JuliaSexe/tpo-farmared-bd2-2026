"""Pruebas de regresión para ajustes de noviembre de 2026 (sin escrituras)."""
import unittest
from unittest.mock import MagicMock
from src.consultas.consistencia_redis import verificar_proyecciones, verificar_mes_sin_ventas
from src.servicios.q13_abm_clientes import validar_cobertura, alta_cliente, modificar_cliente


class TestConsistenciaRedis(unittest.TestCase):
    def test_no_publicado(self):
        db, redis = MagicMock(), MagicMock()
        redis.exists.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'no fue construido'):
            verificar_proyecciones(db, redis)

    def test_pendientes_rechazados(self):
        db, redis = MagicMock(), MagicMock()
        redis.exists.return_value = True
        db.ventas.count_documents.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'pendientes'):
            verificar_proyecciones(db, redis)

    def test_publicado_sin_pendientes(self):
        db, redis = MagicMock(), MagicMock()
        redis.exists.return_value = True
        db.ventas.count_documents.return_value = 0
        verificar_proyecciones(db, redis)

    def test_mes_vacio(self):
        db = MagicMock()
        db.ventas.count_documents.return_value = 0
        self.assertTrue(verificar_mes_sin_ventas(db, '2026-12'))
        db.ventas.count_documents.return_value = 1
        self.assertFalse(verificar_mes_sin_ventas(db, '2026-12'))


class TestCobertura(unittest.TestCase):
    def test_sin_cobertura_no_admite_afiliado(self):
        with self.assertRaises(ValueError):
            validar_cobertura({'obra_social': 'Sin cobertura', 'nro_afiliado': 'ABC'})

    def test_con_cobertura_exige_afiliado(self):
        with self.assertRaises(ValueError):
            validar_cobertura({'obra_social': 'OSDE', 'nro_afiliado': None})

    def test_obras_sociales_permitidas(self):
        with self.assertRaises(ValueError):
            validar_cobertura({'obra_social': 'Inventada', 'nro_afiliado': 'ABC'})

    def test_modificacion_limpia_afiliado(self):
        db = MagicMock()
        db.clientes.find_one.return_value = {'_id': 'C001', 'obra_social':'OSDE','nro_afiliado':'123'}
        db.clientes.find_one_and_update.return_value = {'obra_social':'Sin cobertura','nro_afiliado':None}
        modificar_cliente(db, 'C001', {'obra_social':'Sin cobertura'})
        update = db.clientes.find_one_and_update.call_args.args[1]['$set']
        self.assertIsNone(update['nro_afiliado'])

    def test_alta_incompleta_explicita(self):
        db=MagicMock()
        with self.assertRaisesRegex(ValueError, 'Faltan campos'):
            alta_cliente(db, {'id_cliente':'C000'})

if __name__ == '__main__':
    unittest.main()
