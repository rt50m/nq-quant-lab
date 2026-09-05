import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'research6'))
from core61 import enriched_outcomes,select61,path_stats,sized_path,cfg

class R61Tests(unittest.TestCase):
    def test_next_bar_and_reentry(self):
        a=np.zeros((1,390,5),float);a[:,:,0:4]=100.;a[:,:,4]=1000.
        # price rises enough for first target then later second target
        a[0,11,0:4]=[100,102,99.8,101];a[0,12:,0:4]=101
        a[0,21,0:4]=[101,103,100.8,102];a[0,22:,0:4]=102
        atr=np.array([10.]);ev=np.array([[0,10,1],[0,20,1]],np.int32)
        o=enriched_outcomes(a,atr,ev,.2,0.5,30,.25,389)
        tr=select61(o,np.ones(2,dtype=np.bool_),0,360,0,12,0)
        self.assertEqual(len(tr),2);self.assertEqual(int(tr[0,2]),11);self.assertGreater(int(tr[1,2]),int(tr[0,3]))
    def test_stop_first_ambiguity(self):
        a=np.zeros((1,390,5),float);a[:,:,0:4]=100.;a[:,:,4]=1000.;atr=np.array([10.]);ev=np.array([[0,10,1]],np.int32)
        a[0,11]=[100,105,95,100,1000]
        o=enriched_outcomes(a,atr,ev,.2,1.0,30,.0,389)
        self.assertEqual(int(o[0,10]),1);self.assertLess(o[0,5],0)
    def test_path_stats(self):
        p=np.array([100.,-50.,100.]);w=np.array([-20.,-80.,-10.]);x=np.array([1,1,1],bool);days=np.array([0,1,2]);years=np.array([2023,2024,2025])
        s=path_stats(p,w,x,days,years);self.assertEqual(s['net_profit'],150.);self.assertLess(s['max_drawdown'],0);self.assertEqual(s['trades'],3)

if __name__=='__main__':unittest.main()
