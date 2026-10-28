import ctypes as c
import json,pathlib,random,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CPU(c.Structure): _fields_=[(s,c.c_uint) for s in ['id','kind','capacity','thermal_pressure','util','energy_cost','online']]
class Profile(c.Structure): _fields_=[(s,c.c_uint) for s in ['latency_budget_us','migration_hold_us','improvement_permille','energy_weight','latency_weight','observe_only']]
class Task(c.Structure): _fields_=[(s,c.c_uint) for s in ['util','wait_us','interactive','prev_cpu']]+[(s,c.c_uint64) for s in ['allowed_mask','now_us','last_migration_us']]
class State(c.Structure): _fields_=[(s,c.c_uint) for s in ['samples','util_ewma','wait_ewma']]
class Result(c.Structure): _fields_=[('cpu',c.c_int),('may_apply',c.c_uint),('reason',c.c_uint),('score',c.c_uint64)]
class VasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); path=pathlib.Path(cls.tmp.name)/'vas.so'
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-O2','-shared','-fPIC',str(ROOT/'patches/scheduler-vas/vas_core.c'),'-o',str(path)],check=True)
        cls.lib=c.CDLL(str(path)); cls.lib.vas_select.argtypes=[c.POINTER(CPU),c.c_uint,c.POINTER(Profile),c.POINTER(Task)]; cls.lib.vas_select.restype=Result
        cls.lib.vas_update.argtypes=[c.POINTER(State),c.c_uint,c.c_uint]
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.cpus=(CPU*4)(CPU(0,0,320,0,0,100,1),CPU(3,1,700,0,0,200,1),CPU(5,2,760,0,0,190,1),CPU(7,3,1024,0,0,400,1))
        self.p=Profile(4000,4000,120,100,100,1); self.t=Task(200,1000,1,0,0xff,20000,0)
    def select(self): return self.lib.vas_select(self.cpus,4,c.byref(self.p),c.byref(self.t))
    def test_observe_only(self): self.assertEqual(self.select().may_apply,0)
    def test_affinity(self): self.t.allowed_mask=1<<5; self.assertEqual(self.select().cpu,5)
    def test_full_thermal_pressure(self):
        self.t.allowed_mask=1; self.cpus[0].thermal_pressure=320; self.assertEqual(self.select().cpu,-1)
    def test_offline(self):
        self.t.allowed_mask=1; self.cpus[0].online=0; self.assertEqual(self.select().cpu,-1)
    def test_peak_demand(self): self.t.util=900; self.assertEqual(self.select().cpu,7)
    def test_a710_a715_distinct_costs(self):
        self.t.allowed_mask=(1<<3)|(1<<5); self.assertEqual(self.select().cpu,5)
        self.cpus[2].energy_cost=1000; self.assertEqual(self.select().cpu,3)
    def test_hysteresis(self):
        self.t.prev_cpu=7; self.t.last_migration_us=19999; self.assertEqual(self.select().cpu,7); self.assertEqual(self.select().reason,1)
    def test_hold_cannot_override_thermal(self):
        self.t.last_migration_us=19999; self.cpus[0].thermal_pressure=320; self.assertNotEqual(self.select().cpu,0)
    def test_duplicate_ids(self): self.cpus[1].id=0; self.assertEqual(self.select().reason,3)
    def test_clock_rollback(self): self.t.last_migration_us=20001; self.assertEqual(self.select().reason,3)
    def test_ewma_bounded(self):
        s=State(); self.lib.vas_update(c.byref(s),800,10000); self.lib.vas_update(c.byref(s),0,0)
        self.assertEqual(s.util_ewma,700); self.assertEqual(s.wait_ewma,8750)
        self.lib.vas_update(c.byref(s),1025,1); self.assertEqual(s.samples,2)
    def test_fuzz_affinity_thermal_invariants(self):
        rng=random.Random(8550)
        for _ in range(10000):
            self.t.util=rng.randrange(1025); self.t.allowed_mask=rng.randrange(256)
            for cpu in self.cpus:
                cpu.thermal_pressure=rng.randrange(cpu.capacity+1); cpu.online=rng.randrange(2); cpu.util=rng.randrange(1025)
            r=self.select()
            if r.cpu>=0:
                cpu=next(x for x in self.cpus if x.id==r.cpu)
                self.assertTrue(cpu.online and self.t.allowed_mask&(1<<cpu.id)); self.assertLessEqual(self.t.util,cpu.capacity-cpu.thermal_pressure)
            self.assertEqual(r.may_apply,0)
    def test_synthetic_replay(self):
        reports=[]
        for mode in ['balanced','performance','efficiency']:
            d=json.loads((ROOT/'configs'/mode/'vas.json').read_text()); self.p=Profile(*(int(d[s]) for s,_ in Profile._fields_))
            prev=0; migrations=0; rejected=0; choices={str(i):0 for i in [0,3,5,7]}
            for i in range(600):
                self.t=Task([100,250,550,900,100,400][i%6],i%8*1000,1,prev,255,i*2000,0)
                self.cpus[3].thermal_pressure=256 if i%20<10 else 0
                r=self.select()
                if r.cpu<0: rejected+=1; continue
                choices[str(r.cpu)]+=1; migrations+=r.cpu!=prev; prev=r.cpu
            reports.append({'mode':mode,'synthetic_decision_changes':migrations,'no_feasible_cpu':rejected,'choices':choices})
        (ROOT/'evidence/vas-synthetic-replay.json').write_text(json.dumps({'synthetic':True,'device_latency_or_power_measured':False,'results':reports},indent=2)+'\n')

if __name__=='__main__': unittest.main()
