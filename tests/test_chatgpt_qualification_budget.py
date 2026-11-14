import json
from pathlib import Path
import tempfile
import unittest
from tools.qualify_chatgpt_features import FeatureBudget


class QualificationBudgetTests(unittest.TestCase):
    def test_each_feature_reserves_once_even_after_an_uncertain_response(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'preflight-qualification.json').write_text(json.dumps({
                'state': 'passed', 'inference_calls': 1, 'model': 'fixture'}))
            budget = FeatureBudget(root, 'fixture')
            for feature in ('F1', 'F2', 'F3', 'F4', 'F5'):
                budget.reserve(feature)
                with self.assertRaises(FileExistsError): budget.reserve(feature)
            self.assertEqual(len(list(budget.directory.glob('F*.json'))), 5)
            with self.assertRaises(ValueError): budget.reserve('F6')
            budget.record('F1', {'state': 'passed'})
            with self.assertRaises(FileExistsError): budget.reserve('F1')

    def test_no_feature_calls_before_the_passed_gate_or_under_a_different_model(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'preflight-qualification.json').write_text(json.dumps({
                'state': 'failed', 'inference_calls': 1, 'model': 'fixture'}))
            with self.assertRaises(ValueError): FeatureBudget(root, 'fixture')
            Path(root, 'preflight-qualification.json').write_text(json.dumps({
                'state': 'passed', 'inference_calls': 1, 'model': 'fixture'}))
            with self.assertRaises(ValueError): FeatureBudget(root, 'different-model')
