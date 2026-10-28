import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('module_inventory',ROOT/'scripts/audit-modules.py')
inventory=importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

class ModuleInventoryTests(unittest.TestCase):
    def test_empty_inventory_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            report=inventory.audit(d,'','5.15')
        self.assertFalse(report['all_supplied_modules_crc_pass'])
        self.assertFalse(report['inventory_completeness_verified'])

    def test_corrupt_compressed_module_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'bad.ko.gz').write_bytes(b'not gzip')
            report=inventory.audit(d,'','5.15')
        self.assertEqual(report['module_count'],1)
        self.assertEqual(report['crc_pass_count'],0)
        self.assertFalse(report['deployable'])
