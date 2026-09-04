import unittest
import numpy as np
from execution import replay,size,posterior_path


class ExecutionTests(unittest.TestCase):
    def fixture(self,model=31):
        a=np.zeros((1,390,5));a[:,:,:4]=100.;a[:,:,4]=10
        events=np.array([[0,15,1,98,110,np.nan,110,90]],float)
        atr=np.array([20.]);vwap=np.full((1,390),99.)
        aux=np.full((1,390,2),np.nan)
        c=np.array([80,0,0,20,19,0,0,1,1,120],float)
        p=np.zeros(5)
        account=np.array([50000,2000,50100,1000,0,0,4,25,40],float)
        return [a,events,atr,vwap,aux,aux.copy(),model,c,p,account,False,0.]

    def test_whole_nq_first_and_mnq_fallback(self):
        self.assertEqual(size(2,80,0,0,0,4,40)[:2],(2,20.))
        self.assertEqual(size(2,30,0,0,0,4,40)[:2],(7,2.))
        self.assertEqual(size(2,1,0,0,0,4,40)[0],0)

    def test_gap_losses_are_not_clipped(self):
        args=self.fixture();args[0][0,16,:4]=96
        r,*_=replay(*args)
        self.assertEqual(r[0,0],-160)
        self.assertGreater(-r[0,0],args[7][0])

    def test_target_and_stop_same_bar_stop_first(self):
        args=self.fixture();args[0][0,16,1]=111;args[0][0,16,2]=97
        r,*_=replay(*args)
        self.assertEqual(r[0,0],-80);self.assertEqual(r[0,5],1)

    def test_missing_active_path_never_becomes_a_completed_account(self):
        args=self.fixture();args[0][0,16]=np.nan;args[10]=True
        r,balance,status,failed=replay(*args)
        self.assertEqual(r[0,6],1);self.assertEqual(status,2);self.assertEqual(failed,0)
        self.assertEqual(balance,50000)

    def test_partial_profit_then_runner(self):
        args=self.fixture(19);args[8][:2]=[.5,1]
        args[0][0,16,1]=102;args[0][0,20,:4]=104
        r,*_=replay(*args)
        self.assertEqual(r[0,18],1);self.assertEqual(r[0,0],120)
        self.assertEqual(r[0,1],1)

    def test_infeasible_partial_is_not_ordinary_orb(self):
        args=self.fixture(19);args[8][:2]=[.5,1];args[7][0]=40
        r,*_=replay(*args)
        self.assertEqual(r[0,1],0);self.assertEqual(r[0,7],1)

    def test_additions_keep_episode_budget_and_instrument(self):
        args=self.fixture(20);args[7][0]=300;args[8][:3]=[.5,2,.5]
        args[0][0,16:20,:4]=101;args[0][0,17:20,:4]=102
        r,*_=replay(*args)
        self.assertLessEqual(r[0,11],300+1e-8);self.assertLessEqual(r[0,10],4)
        self.assertEqual(r[0,9],0)

    def test_inside_range_is_checked_at_actual_open(self):
        args=self.fixture();args[0][0,15,:4]=111
        r,*_=replay(*args)
        self.assertEqual(r[0,1],0)

    def test_limit_does_not_fill_on_touch(self):
        args=self.fixture(15);args[1][0,5]=100;args[8][0]=3
        r,*_=replay(*args)
        self.assertEqual(r[0,1],0)

    def test_limit_cannot_claim_target_before_fill_same_bar(self):
        args=self.fixture(15);args[1][0,5]=99;args[8][0]=3;args[7][2]=2
        args[0][0,15]=[100,104,98.75,100,10]
        # Stop fixed at 98, actual limit entry 99, target101. The bar's high
        # may precede the limit fill, so conservatively wait for later evidence.
        r,*_=replay(*args)
        self.assertEqual(r[0,13],20);self.assertEqual(r[0,5],1)

    def test_bayesian_joint_probability_reacts_to_adverse_returns(self):
        a=posterior_path(np.r_[np.ones(8)*2,np.ones(5)*-3],1/60,5)
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(a[-1,0],a[7,0])
        self.assertFalse(np.allclose(a[:,0],1/60))


if __name__=='__main__':unittest.main()
