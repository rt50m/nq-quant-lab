"""Execution chronology, accounting, causality and interrupted-checkpoint gates."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from execution import replay,size
from signals import regression,markov_forecast,Features,build
from registry import groups,grid,study_hash
from run import verified_group
from analysis import sequential

def fixture(days=1):
    a=np.full((days,390,5),100.);a[:,:,1]=100.1;a[:,:,2]=99.9;a[:,:,4]=1
    cmd=np.full((days,390),np.nan);st=cmd.copy();target=cmd.copy();end=np.full_like(cmd,389)
    return a,cmd,st,target,end,np.ones(days,dtype=bool),np.full(days,10.)

def run(v,risk=50,entries=3,enforce=False,slip=0.,daily=1000,loss=2000):
    return replay(*v,risk,.1,entries,slip,1.75,.5,50000,loss,50100,daily,25,4,40,enforce)

class ExecutionTests(unittest.TestCase):
    def test_whole_contracts_and_nq_first(self):
        self.assertEqual(size(1,50,0,4,40,1.75,.5)[:2],(2,20.))
        self.assertEqual(size(10,50,0,4,40,1.75,.5)[:2],(2,2.))
        self.assertEqual(size(10,10,0,4,40,1.75,.5)[0],0)

    def test_roundtrip_fees_and_flatten(self):
        v=fixture();v[1][0,1]=1
        r,*_=run(v)
        self.assertAlmostEqual(r[0,0],-7);self.assertEqual(r[0,15],389)
        self.assertEqual(r[0,2],1)

    def test_multiple_entries_charge_every_roundtrip(self):
        v=fixture();v[1][0,[1,3,5,7]]=[1,0,-1,0]
        r,*_=run(v)
        self.assertEqual(r[0,2],2);self.assertAlmostEqual(r[0,0],-14)
        self.assertAlmostEqual(r[0,17],-7);self.assertAlmostEqual(r[0,18],-7)

    def test_resize_only_delta_is_charged(self):
        v=fixture();v[1][0,[1,2,3,4]]=[.5,1,.5,0]
        r,*_=run(v)
        self.assertAlmostEqual(r[0,0],-7);self.assertEqual(r[0,2],1)

    def test_stop_target_ambiguity_is_stop_first(self):
        v=fixture();v[1][0,1]=1;v[3][0,1]=101
        v[0][0,1,1:3]=[102,98]
        r,*_=run(v)
        self.assertEqual(r[0,6],1);self.assertAlmostEqual(r[0,0],-47)

    def test_gap_is_not_clipped(self):
        v=fixture();v[1][0,1]=1;v[0][0,2,:4]=[90,90.1,89.9,90]
        r,*_=run(v)
        self.assertAlmostEqual(r[0,0],-407)

    def test_daily_lockout_persists(self):
        v=fixture();v[1][0,[1,3]]=1;v[0][0,2,:4]=[90,90.1,89.9,90]
        r,*_=run(v,daily=100)
        self.assertEqual(r[0,10],1);self.assertGreater(r[0,9],0)

    def test_reversal_costs_and_no_overlap(self):
        v=fixture();v[1][0,[1,3,5]]=[1,-1,0]
        r,*_=run(v)
        self.assertEqual(r[0,2],2);self.assertAlmostEqual(r[0,0],-14)

    def test_missing_active_path_stops_account(self):
        v=fixture(2);v[1][:,1]=1;v[0][0,3]=np.nan
        r,b,status,d=run(v,enforce=True)
        self.assertEqual(status,2);self.assertEqual(d,0);self.assertEqual(r[1,10],0)

    def test_unrelated_missing_flat_bar_is_not_trade_gap(self):
        v=fixture();v[0][0,5]=np.nan;v[1][0,360]=1
        r,*_=run(v)
        self.assertEqual(r[0,7],0);self.assertEqual(r[0,2],1)

    def test_required_missing_signal_is_unknown(self):
        v=fixture();v[0][0,5]=np.nan;v[1][0,5]=np.inf
        r,b,status,d=run(v,enforce=True)
        self.assertEqual(status,2)

    def test_missing_forced_exit_is_not_fabricated(self):
        v=fixture();v[1][0,1]=1;v[0][0,389]=np.nan
        r,*_=run(v)
        self.assertEqual(r[0,7],1);self.assertEqual(r[0,2],0)

    def test_time_exit_does_not_use_future_bar_extreme(self):
        v=fixture();v[1][0,1]=1;v[4][0,1]=3;v[0][0,3,2]=10
        r,*_=run(v)
        self.assertAlmostEqual(r[0,0],-7);self.assertEqual(r[0,15],3)

    def test_no_new_position_at_flat_deadline(self):
        v=fixture();v[1][0,389]=1
        r,*_=run(v)
        self.assertEqual(r[0,10],0)

    def test_entry_limit_is_not_reset_after_exit(self):
        v=fixture();v[1][0,[1,3,5,7]]=[1,0,1,0]
        r,*_=run(v,entries=1)
        self.assertEqual(r[0,10],1);self.assertEqual(r[0,9],1)

class ForecastTests(unittest.TestCase):
    def test_regression_does_not_train_on_current_target(self):
        rng=np.random.default_rng(12);x=rng.normal(size=(200,3));y=x[:,0]*.01+rng.normal(size=200)*.001
        before=regression(x,y,126)[0];y[150:]=1e6;after=regression(x,y,126)[0]
        np.testing.assert_allclose(before[:151],after[:151],equal_nan=True)

    def test_markov_never_uses_current_or_future_target(self):
        rng=np.random.default_rng(1);x=rng.normal(size=160)*.01;y=x*.2+rng.normal(size=160)*.001
        before=markov_forecast(x,y,252,2)[0];self.assertGreater(np.isfinite(before).sum(),0);y[145:]=5
        after=markov_forecast(x,y,252,2)[0]
        np.testing.assert_allclose(before[:146],after[:146],equal_nan=True)

    def test_month_selection_ignores_test_month(self):
        dates=np.array([str(d.date()) for d in __import__('pandas').bdate_range('2023-01-01',periods=200)])
        daily=np.array([np.ones(200),np.full(200,.5)]);known=np.ones_like(daily,dtype=bool)
        _,_,a=sequential(['a','b'],daily,known,known,dates)
        last=dates[-1][:7];daily[1,np.array([d[:7]==last for d in dates])]=1000
        _,_,b=sequential(['a','b'],daily,known,known,dates)
        self.assertEqual(a,b)

class ManifestTests(unittest.TestCase):
    def test_exactly_ten_families_and_unique_configs(self):
        gs=list(groups());cs=[c for _,_,v in gs for c in v]
        self.assertEqual(len({c['id'] for c in cs}),len(cs))
        self.assertEqual({s['family'] for _,s,_ in gs if not s['control']},{f'M{i:02d}' for i in range(1,11)})

    def test_partial_block_is_not_a_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'group-0000.json';p.write_text('{}')
            self.assertIsNone(verified_group(p,[],'data'))

    def test_foreign_code_checkpoint_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'group-0000.json';p.with_suffix('.npz').write_bytes(b'fake')
            p.write_text(json.dumps({'study_hash':'foreign','data_hash':'data'}))
            with self.assertRaises(ValueError):verified_group(p,[],'data')

if __name__=='__main__':unittest.main()
