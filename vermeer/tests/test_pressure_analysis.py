import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('pressure_analysis', Path(__file__).resolve().parents[1] / 'scripts/analyze-pressure.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def capture(boot='test-boot', counter=1256, total=300000, missing=False):
    rows = []
    for i in range(2):
        rows += ['SAMPLE ' + str(i), 'PATH /proc/uptime', str(100 + 10 * i),
                 'PATH UPTIME_END', str(100 + 10 * i),
                 'PATH /proc/sys/kernel/random/boot_id', 'test-boot' if not i else boot,
                 'PATH PAGE_SIZE', '4096', 'PATH /proc/vmstat',
                 'pswpin ' + str(1000 if not i else counter)]
        if not (missing and i):
            rows += ['PATH /proc/pressure/memory',
                     'some avg10=0.0 total=' + str(100000 if not i else total),
                     'full avg10=0.0 total=0']
        rows += ['END_SAMPLE']
    return '\n'.join(rows + [module.COMPLETE, ''])


class PressureTests(unittest.TestCase):
    def test_delta_units_and_no_cpu_full_claim(self):
        result = module.analyze(capture())
        w = result['windows'][0]
        self.assertAlmostEqual(w['psi']['memory']['some']['approx_wall_time_percent'], 2)
        self.assertAlmostEqual(w['swap']['pswpin_MiB_per_second'], 0.1)
        self.assertNotIn('full', w['psi']['cpu'])
        self.assertFalse(result['controlled_benchmark'])

    def test_reboot_is_refused(self):
        with self.assertRaises(ValueError): module.analyze(capture(boot='other-boot'))

    def test_truncated_capture_is_refused(self):
        with self.assertRaises(ValueError): module.analyze(capture().replace(module.COMPLETE, ''))

    def test_missing_pressure_is_unknown(self):
        w = module.analyze(capture(missing=True))['windows'][0]
        self.assertIsNone(w['psi']['memory']['some'])

    def test_reset_counter_is_unknown(self):
        w = module.analyze(capture(counter=2, total=1))['windows'][0]
        self.assertIsNone(w['swap']['pswpin_MiB_per_second'])
        self.assertIsNone(w['psi']['memory']['some'])

    def test_impossible_psi_is_unknown(self):
        w = module.analyze(capture(total=999999999))['windows'][0]
        self.assertIsNone(w['psi']['memory']['some'])

    def test_nonfinite_time_is_refused(self):
        with self.assertRaises(ValueError): module.analyze(capture().replace('100\n', 'nan\n'))
