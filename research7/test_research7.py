import unittest, numpy as np
import tempfile
from pathlib import Path
from adapters import load_spec
from portfolio import mdd_from_daily, exact_metrics
from sleeves import trade_sizing

class TestR7(unittest.TestCase):
    def test_daily_mdd(self):
        self.assertAlmostEqual(mdd_from_daily(np.array([100,-50,-100,80.])), -150.0)
    def test_exact_path(self):
        dates=np.array(['2023-01-03'])
        d=np.zeros(390);a=np.zeros(390);e=np.zeros(390,dtype=int)
        a[10]=-100;d[20]=50
        s=exact_metrics(d,a,e,dates)
        self.assertEqual(s['net_profit'],50.0);self.assertEqual(s['max_drawdown'],-100.0)

    def test_dynamic_dataclass_import_py312(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mod.py'
            p.write_text('from __future__ import annotations\nfrom dataclasses import dataclass\n@dataclass\nclass X:\n    value: int\n')
            m=load_spec('r7_test_dataclass_mod',p)
            self.assertEqual(m.X(3).value,3)

    def test_risk_sizing(self):
        t=np.array([[0,1,2,1,1.0,-1.0,10.0,100.0]])
        ok,pv,comm,q,ex=trade_sizing(t,'RISK',125)
        self.assertTrue(ok[0]);self.assertGreater(q[0],0);self.assertLessEqual(ex[0],40)

if __name__=='__main__':unittest.main()
