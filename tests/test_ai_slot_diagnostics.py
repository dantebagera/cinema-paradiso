import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace

from tools.ai_slot_diagnostics import SlotDiagnostics
from services.ai_jobs import AIJobStore


class SlotDiagnosticTests(unittest.TestCase):
    def test_actual_operation_clock_excludes_slow_diagnostic_writes(self):
        with tempfile.TemporaryDirectory(prefix='cp-slot-test-') as root:
            clock = [0.0]
            def slow_emit(*args, **kwargs):
                clock[0] += 5.85
            trace = SimpleNamespace(emit=slow_emit)
            diagnostic = SlotDiagnostics(root, trace, clock=lambda: clock[0])
            diagnostic.start()
            try:
                trace.emit('span_start', phase='lease_acquire', label='synthetic', function='synthetic')
                with diagnostic.operation('slot_acquire_actual'):
                    clock[0] += .01
                trace.emit('span_end', phase='lease_acquire', label='synthetic', function='synthetic')
            finally:
                diagnostic.close()
            actual = next(row for row in diagnostic.samples if row['phase']=='slot_acquire_actual')
            writes = [row for row in diagnostic.samples if row['phase']=='trace_emit']
            self.assertAlmostEqual(actual['seconds'], .01)
            self.assertTrue(all(abs(row['seconds']-5.85)<1e-6 for row in writes))

    def test_sqlite_semantics_hook_restoration_and_idempotent_close(self):
        with tempfile.TemporaryDirectory(prefix='cp-slot-test-') as root:
            trace = SimpleNamespace(emit=lambda *a, **kw: None)
            original_connect, original_emit = sqlite3.connect, trace.emit
            diagnostic = SlotDiagnostics(root, trace)
            diagnostic.start()
            try:
                store = AIJobStore(Path(root)/'user-data')
                with diagnostic.operation('slot_acquire_actual'):
                    first = store.acquire_inference_slot('synthetic')
                store.release_inference_slot(first)
                other = AIJobStore(Path(root)/'user-data')
                first, second = store.acquire_inference_slot('one'), other.acquire_inference_slot('two')
                self.assertIsNone(store.acquire_inference_slot('third'))
                store.release_inference_slot(first)
                other.release_inference_slot(second)
            finally:
                diagnostic.close()
                diagnostic.close()
            self.assertIs(sqlite3.connect, original_connect)
            self.assertIs(trace.emit, original_emit)
            self.assertTrue(any(row['phase']=='sqlite_commit' for row in diagnostic.samples))
            self.assertTrue(any(row['phase']=='sqlite_close' for row in diagnostic.samples))
            self.assertTrue((Path(root)/'slot-diagnostics.json').is_file())

    def test_non_temp_root_is_refused(self):
        with self.assertRaises(ValueError):
            SlotDiagnostics(Path.cwd(), SimpleNamespace(emit=lambda *a, **kw: None))

    def test_explicit_connection_factory_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix='cp-slot-test-') as root:
            database = Path(root)/'user-data/ai/ai.sqlite'
            database.parent.mkdir(parents=True)
            diagnostic = SlotDiagnostics(root, SimpleNamespace(emit=lambda *a, **kw: None))
            class Custom(sqlite3.Connection):
                pass
            diagnostic.start()
            try:
                connection = sqlite3.connect(database, factory=Custom)
                try:
                    self.assertIsInstance(connection, Custom)
                    self.assertEqual(connection.execute('SELECT 1').fetchone(), (1,))
                finally:
                    connection.close()
            finally:
                diagnostic.close()

    def test_non_target_database_and_sql_parameters_are_not_recorded(self):
        with tempfile.TemporaryDirectory(prefix='cp-slot-test-') as root:
            diagnostic = SlotDiagnostics(root, SimpleNamespace(emit=lambda *a, **kw: None))
            diagnostic.start()
            try:
                with sqlite3.connect(':memory:') as connection:
                    connection.execute('SELECT ?', ('SECRET_VALUE',)).fetchone()
                self.assertEqual(diagnostic.samples, [])
                store = AIJobStore(Path(root)/'user-data')
                store.acquire_inference_slot('SECRET_VALUE')
            finally:
                diagnostic.close()
            self.assertNotIn('SECRET_VALUE', json.dumps(diagnostic.samples))
