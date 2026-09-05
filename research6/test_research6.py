import unittest, tempfile, json
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from registry import group_count,execution_count,total_count,config
from execution import outcomes,select
from sizing import evaluate

class TestR6(unittest.TestCase):
    def test_frozen_grid_count(self):
        self.assertEqual(group_count(),390)
        self.assertEqual(execution_count(),540)
        self.assertEqual(total_count(),210600)
    def test_next_bar_entry_and_reentry(self):
        a=np.full((1,390,5),100.0);a[:,:,1]=101;a[:,:,2]=99;a[:,:,4]=1
        atr=np.array([10.0]);ev=np.array([[0,10,1],[0,12,1],[0,20,1]],dtype=np.int32)
        o=outcomes(a,atr,ev,.2,0,3,.25,389)
        self.assertEqual(int(o[0,2]),11)
        tr=select(o,0,360,1,12)
        self.assertTrue(np.all(tr[:,2]>tr[:,1]))
        self.assertLess(len(tr),len(ev))  # overlapping signal is skipped while position is open
    def test_stop_first(self):
        a=np.full((1,390,5),100.0);a[:,:,1]=100;a[:,:,2]=100;a[:,:,4]=1
        a[0,11]=[100,105,95,100,1]  # both stop and target hit
        atr=np.array([10.0]);ev=np.array([[0,10,1]],dtype=np.int32)
        o=outcomes(a,atr,ev,.2,1.0,10,.25,389)
        self.assertLess(o[0,5],0)
    def test_fixed_qty_scaling_under_cap(self):
        # synthetic trade path with small unit DD should scale quantity, but never exceed configured cap
        t=np.array([[0,0,1,2,1,2.0,-1.0,2.0],[1,0,1,2,1,-1.0,-1.0,2.0],[2,0,1,2,1,2.0,-.5,2.0]],float)
        dates=np.array(['2023-01-03','2024-01-03','2025-01-03'])
        r=evaluate(t,dates);self.assertIsNotNone(r);self.assertGreater(r['max_drawdown'],-config()['objective']['max_drawdown'])

if __name__=='__main__':unittest.main()
