import unittest
import numpy as np
from discover import mask_rule
from backtest import size

class TestR5(unittest.TestCase):
    def test_rule_mask(self):
        X=np.array([[1.,2.],[3.,4.],[5.,1.]])
        names=['a','b']
        m=mask_rule(X,names,[('a','>',2),('b','<=',4)])
        self.assertEqual(m.tolist(),[False,True,True])
    def test_sizing_caps(self):
        self.assertEqual(size(1.0,300)[0],'NQ')
        self.assertLessEqual(size(1.0,300)[1],4)
        tiny=size(100.0,300)
        self.assertTrue(tiny is None or tiny[1] <= 40)

if __name__=='__main__':unittest.main()
