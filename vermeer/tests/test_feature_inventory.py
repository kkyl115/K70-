import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('feature_inventory',ROOT/'scripts/audit-features.py')
feature=importlib.util.module_from_spec(spec)
spec.loader.exec_module(feature)

class FeatureInventoryTests(unittest.TestCase):
    def test_absent_is_unknown_and_module_is_not_runtime_proof(self):
        report=feature.audit(b'CONFIG_ZRAM=m\n# CONFIG_PID_NS is not set\n')
        self.assertEqual(report['features']['ZRAM']['CONFIG_ZRAM'],'m')
        self.assertEqual(report['features']['DroidSpaces']['CONFIG_PID_NS'],'n')
        self.assertEqual(report['features']['NTSync']['CONFIG_NTSYNC'],'not_recorded')
        self.assertFalse(report['runtime_verified'])

    def test_full_config_never_authorizes_deployment(self):
        keys={k for values in feature.FEATURES.values() for k in values}
        report=feature.audit(('\n'.join(k+'=y' for k in keys)).encode())
        self.assertEqual(report['droidspaces_core_requirements_not_shown_enabled'],[])
        self.assertTrue(report['susfs_container_visibility_review_required'])
        self.assertFalse(report['abi_verified'])
        self.assertFalse(report['deployable'])
