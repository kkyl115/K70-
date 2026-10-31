import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('adb_collect', Path(__file__).resolve().parents[1] / 'scripts/collect-adb-readonly.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AdbReadOnlyTests(unittest.TestCase):
    def test_no_device_or_not_authorized_is_refused(self):
        for rows in ([], [('test', 'unauthorized')], [('test', 'offline')]):
            with self.assertRaises(ValueError):
                module.select_device(rows)

    def test_one_device_does_not_override_another_offline(self):
        with self.assertRaises(ValueError):
            module.select_device([('one', 'device'), ('two', 'offline')])

    def test_valid_inventory(self):
        rows = module.device_rows('List of devices attached\nexample\tdevice\n\n')
        self.assertEqual(module.select_device(rows), 'example')

    def test_error_not_mistaken_for_inventory(self):
        with self.assertRaises(ValueError):
            module.device_rows('error: no devices')

    def test_wrong_model_and_root_refused(self):
        for model in ('', 'vermeer_test', 'kalama'):
            with self.assertRaises(ValueError): module.require_vermeer(model)
        module.require_vermeer('vermeer\r\n')
        with self.assertRaises(ValueError): module.require_root('uid=2000(shell)')
        module.require_root('uid=0(root) gid=0(root)')
