import unittest
import numpy as np
from signals import orb_events
from run import read,save
from pathlib import Path
import tempfile


class SequenceTests(unittest.TestCase):
    def fixture(self):
        a=np.zeros((1,390,5));a[:,:,:4]=100;a[:,:,4]=10
        a[0,:30,1]=105;a[0,:30,2]=95
        a[0,42:,:4]=106
        return a,np.array([True]),np.array([20.]),np.zeros((1,3)),np.full((1,390),100.)

    def test_serial_transition_requires_completed_nonoverlapping_blocks(self):
        a,keep,atr,night,vwap=self.fixture()
        p=np.zeros(12);p[:5]=[30,20,2,.5,10]
        daily=np.full((1,3),np.nan);aux=np.full((1,390,2),np.nan)
        aux[0,20,0]=-1;aux[0,40,0]=1
        result=orb_events(a,keep,atr,night,vwap,27,p,daily,aux)
        self.assertEqual(result[0,43,0],1)
        self.assertFalse(np.isfinite(result[0,:43,0]).any())
        aux[0,20,0]=1
        self.assertFalse(np.isfinite(orb_events(a,keep,atr,night,vwap,27,p,daily,aux)[:,:,0]).any())

    def test_spread_gate_waits_for_two_complete_blocks(self):
        a,keep,atr,night,vwap=self.fixture()
        p=np.zeros(12);p[0]=15;p[4]=.05
        daily=np.array([[.001,.002,np.nan]]);aux=np.full((1,390,2),np.nan)
        result=orb_events(a,keep,atr,night,vwap,30,p,daily,aux)
        self.assertEqual(result[0,43,0],1)
        daily[0,0]=-.001
        self.assertFalse(np.isfinite(orb_events(a,keep,atr,night,vwap,30,p,daily,aux)[:,:,0]).any())

    def test_checkpoint_rejects_different_code_or_configs(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'group.json.gz';identity={'study_hash':'one'};c={'id':'first'}
            save(p,{'identity':identity,'rows':[{'config':c,'net':1}]})
            self.assertEqual(len(read(p,identity,[c])),1)
            with self.assertRaises(ValueError):read(p,{'study_hash':'two'},[c])
            with self.assertRaises(ValueError):read(p,identity,[{'id':'second'}])


if __name__=='__main__':unittest.main()
