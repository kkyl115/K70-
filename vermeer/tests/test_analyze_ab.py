import csv,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from analyze_ab import analyze
class ABTests(unittest.TestCase):
    def file(self,rows):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); p=pathlib.Path(tmp.name)/'synthetic.csv'
        with p.open('w',newline='') as f:
            w=csv.writer(f); w.writerow('pair variant workload latency_p95_ms latency_p99_ms jank_percent energy_j thermal_max_c battery_start_percent duration_s'.split()); w.writerows(rows)
        return p
    def test_paired_math(self):
        p=self.file([['1','baseline','synthetic',5,10,3,100,35,80,60],['1','candidate','synthetic',4,9,2,90,34,80,60]])
        r=analyze(p)['workloads']['synthetic']; self.assertEqual(r['energy_j']['median_candidate_minus_baseline'],-10); self.assertTrue(r['energy_j']['needs_more_runs'])
    def test_unpaired_rejected(self):
        with self.assertRaises(ValueError): analyze(self.file([['1','baseline','synthetic',5,10,3,100,35,80,60]]))
    def test_nan_rejected(self):
        with self.assertRaises(ValueError): analyze(self.file([['1','baseline','synthetic','nan',10,3,100,35,80,60]]))
