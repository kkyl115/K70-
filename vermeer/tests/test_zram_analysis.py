import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('zram_analysis', Path(__file__).resolve().parents[1] / 'scripts/analyze-zram.py')
zram = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zram)


class ZramAnalysisTests(unittest.TestCase):
    def test_allocator_cost_not_payload_or_disksize(self):
        r = zram.analyze('8192 2048 4096 0 4096 0 0 0')
        self.assertEqual(r['payload_compression_ratio'], 4)
        self.assertEqual(r['effective_ratio_including_allocator'], 2)
        self.assertEqual(r['net_memory_saved_bytes'], 4096)
        self.assertFalse(r['performance_improvement_verified'])

    def test_empty_and_same_page_counters(self):
        self.assertIsNone(zram.analyze('0 0 0')['effective_ratio_including_allocator'])
        self.assertIsNone(zram.analyze('4096 0 0')['payload_compression_ratio'])

    def test_negative_savings_are_preserved(self):
        self.assertEqual(zram.analyze('4096 4096 8192')['net_memory_saved_bytes'], -4096)

    def test_bad_counters(self):
        for bad in ('', '0 0', '1 -1 0', 'NaN 0 0', '1.2 3 4', '1 2 '+str(1 << 64)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                zram.analyze(bad)
