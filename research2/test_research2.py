import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from engine import execute_day, simulate, quantity, floor_after_close
from run import Features, all_configs, read_grid, signals, study_hash, FAMILIES


class ExecutionTests(unittest.TestCase):
    def bars(self):
        a=np.zeros((960,5));a[:,:4]=100;a[:,4]=1
        return a

    def trade(self,a,**overrides):
        p=dict(entry_minute=600,side=1,distance=2.,target_r=1.,exit_minute=605,trailing=0,
               risk=300.,slip=.25,nq_comm=1.75,mnq_comm=.5,max_nq=4,max_mnq=40,
               daily_limit=1000.,account_allowance=2000.,account_buffer=25.)
        p.update(overrides)
        return execute_day(a,**p)

    def test_stop_target_same_bar_is_stop_first(self):
        a=self.bars();a[601,1]=104;a[601,2]=95
        r=self.trade(a)
        self.assertEqual(r[3],1);self.assertEqual(r[6],1);self.assertLess(r[0],0)

    def test_target_gap_happens_before_later_low(self):
        a=self.bars();a[601,:4]=[104,105,90,101]
        r=self.trade(a)
        self.assertEqual(r[3],2);self.assertEqual(r[6],0)
        # Limit filled at target, not the better opening quote.
        self.assertAlmostEqual(r[0],2*r[4]*r[5]-3.5*r[4])

    def test_gap_loss_is_not_clipped_to_budget(self):
        a=self.bars();a[601,:4]=[70,71,69,70]
        r=self.trade(a)
        self.assertLess(r[0],-1000)

    def test_forced_exit_uses_open_not_future_candle(self):
        a=self.bars();a[605,:4]=[101,120,90,115]
        r=self.trade(a)
        self.assertEqual(r[3],3);self.assertEqual(r[2],605)
        self.assertAlmostEqual(r[0],.5*r[4]*r[5]-3.5*r[4])

    def test_breakeven_activates_next_bar(self):
        a=self.bars();a[601,:4]=[100,103,99,103]
        a[602,:4]=[103,104,100,101]
        r=self.trade(a,target_r=0,trailing=1)
        self.assertEqual(r[2],602);self.assertEqual(r[3],1)

    def test_missing_exit_never_invents_earlier_close(self):
        a=self.bars();a[605,:]=np.nan
        r=self.trade(a)
        self.assertEqual(r[3],7);self.assertEqual(r[7],1)

    def test_account_budget_prevents_new_risk_at_floor(self):
        r=self.trade(self.bars(),account_allowance=20.)
        self.assertEqual(r[3],6);self.assertEqual(r[4],0)

    def test_fee_and_slippage_in_position_budget(self):
        q,pv,fee=quantity(50,300,.25,1.75,.5,4,40)
        self.assertEqual(pv,2)
        self.assertLessEqual(q*((50+.25)*pv+2*fee),300)

    def test_short_symmetry(self):
        a=self.bars();a[601,:4]=[100,104,96,100]
        r=self.trade(a,side=-1)
        self.assertEqual(r[3],1);self.assertEqual(r[6],1)

    def test_eod_floor_cannot_fall_and_locks(self):
        self.assertEqual(floor_after_close(48000,51000,2000,50100),49000)
        self.assertEqual(floor_after_close(49000,50500,2000,50100),49000)
        self.assertEqual(floor_after_close(49000,60000,2000,50100),50100)

    def test_account_stops_after_gap_breach(self):
        a=np.stack([self.bars(),self.bars()]);a[0,601,:4]=[60,61,59,60]
        r,b,status,day,_=simulate(a,np.array([600,600]),np.array([1,1]),np.array([20.,20.]),
             np.array([605,605]),300.,.1,1.,0,.25,1.75,.5,50000.,2000.,50100.,1000.,25.,4,40,True)
        self.assertEqual(status,1);self.assertEqual(day,0);self.assertEqual(r[1,4],0)
        self.assertLess(b,48000)

    def test_missing_intratrade_bar_stops_account_as_unknown(self):
        a=np.stack([self.bars(),self.bars()]);a[0,601,:]=np.nan
        _,_,status,_,_=simulate(a,np.array([600,600]),np.array([1,1]),np.array([20.,20.]),
             np.array([605,605]),300.,.1,1.,0,.25,1.75,.5,50000.,2000.,50100.,1000.,25.,4,40,True)
        self.assertEqual(status,2)


class CausalityTests(unittest.TestCase):
    def fixture(self,directory):
        n=50;a=np.ones((n,960,5));a[:,:,:4]=100
        a[:,570:600,1]=101;a[:,570:600,2]=99
        a[:,600:,0]=102;a[:,600:,1]=103;a[:,600:,2]=101;a[:,600:,3]=102
        # Trend known at range close, followed by a later breakout.
        a[:,584,3]=100.75
        np.save(directory/'bars.npy',a)
        import pandas as pd
        dates=pd.bdate_range('2023-01-02',periods=n).strftime('%Y-%m-%d').tolist()
        (directory/'prepared.json').write_text(json.dumps({'study_hash':study_hash(),'dates':dates,
           'normal_session_mask':[True]*n,'cash_close_minutes':[960]*n,'data_hash':'synthetic'}))
        return a

    def test_future_price_mutation_cannot_change_earlier_signals(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=self.fixture(p)
            f=Features(p)
            for family in ['ORB_BASE','ORB_VWAP','ORB_OPEN_TREND']:
                s=dict(family=family,length=15,confirmation=1,direction=0,buffer_atr=0,minimum_body_fraction=0)
                e,z=signals(f,s)
                changed=a.copy();changed[-1,700:,:4]*=3
                np.save(p/'bars.npy',changed)
                g=Features(p);e2,z2=signals(g,s)
                np.testing.assert_equal(e,e2);np.testing.assert_equal(z,z2)
                self.assertEqual(e[-1],601)
                np.save(p/'bars.npy',a)

    def test_daily_atr_cannot_use_current_day(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=self.fixture(p);f=Features(p);old=f.atr[-1]
            a[-1,700:,1]+=500
            np.save(p/'bars.npy',a);g=Features(p)
            self.assertEqual(old,g.atr[-1])

    def test_two_bar_confirmation_delays_entry(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.fixture(p);f=Features(p)
            s=dict(family='ORB_BASE',length=15,confirmation=1,direction=0)
            e,_=signals(f,s);s['confirmation']=2;e2,_=signals(f,s)
            self.assertEqual(e2[-1],e[-1]+1)

    def test_missing_earlier_signal_bar_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=self.fixture(p)
            a[-1,590,:]=np.nan
            np.save(p/'bars.npy',a);f=Features(p)
            e,_=signals(f,dict(family='ORB_BASE',length=15,confirmation=1,direction=0))
            self.assertEqual(-e[-1]-2,590)

    def test_signal_gap_after_configuration_exit_is_irrelevant(self):
        a=np.zeros((960,5))
        r=execute_day(a,-802,1,2.,1.,690,0,300.,.25,1.75,.5,4,40,1000.,2000.,25.)
        self.assertEqual(r[7],0)

    def test_short_session_not_traded_but_is_previous_close(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=self.fixture(p)
            meta=json.loads((p/'prepared.json').read_text());meta['normal_session_mask'][-2]=False
            meta['cash_close_minutes'][-2]=780
            a[-2,779,3]=110
            np.save(p/'bars.npy',a);(p/'prepared.json').write_text(json.dumps(meta))
            f=Features(p)
            self.assertEqual(f.prev[-1],110)
            e,_=signals(f,dict(family='ORB_BASE',length=15,confirmation=1,direction=0))
            self.assertEqual(e[-2],-1)

    def test_grid_has_ten_models_plus_control_and_all_risks(self):
        counts={f:0 for f in FAMILIES};risks=set();seen=set()
        for c in all_configs(read_grid()):
            self.assertNotIn(c['id'],seen);seen.add(c['id'])
            counts[c['signal']['family']]+=1;risks.add(c['risk'])
            self.assertLessEqual(c['exit'],959)
        self.assertEqual(len(counts),11);self.assertTrue(all(counts.values()))
        self.assertEqual(risks,set(read_grid()['risk_budgets']))


if __name__=='__main__': unittest.main()
