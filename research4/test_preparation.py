import math
import unittest
from unittest.mock import patch
from registry import grid, configs, require_execution_ready


class PreparationTests(unittest.TestCase):
    def test_roster_and_family_coverage(self):
        g=grid()
        self.assertEqual([m['id'] for m in g['models']],[f'R4-{i:02}' for i in range(1,32)])
        self.assertEqual({b['family'][0] for b in g['models'][-1]['blocks']},set('ABCDEFGHIJ'))

    def test_conditional_axes_do_not_multiply_inactive_settings(self):
        for block in grid()['models'][-1]['blocks']:
            family=block['family'][0]
            if family=='D':
                self.assertEqual('body_multiple' in block,block['displacement'][0])
                self.assertEqual('expiry' in block,block['schedule']==['retest'])
            if family=='G':
                self.assertEqual('expiry' in block,block['schedule']==['confirmed'])
            if family in ['E','J']:
                self.assertNotIn('expiry',block)
            self.assertNotIn('target_r',block)
            self.assertNotIn('opening',block)

    def test_declared_menus_are_finite_and_nonempty(self):
        for model in grid()['models']:
            for block in model['blocks']:
                for name,values in block.items():
                    self.assertIsInstance(values,list,name)
                    self.assertGreater(len(values),0,name)
                    for value in values:
                        if isinstance(value,(int,float)):
                            self.assertTrue(math.isfinite(value),name)

    def test_pending_implementations_cannot_be_reported_ready(self):
        with patch('registry.grid',return_value={'models':[{'id':'unimplemented','implementation':'PENDING'}]}):
            with self.assertRaisesRegex(RuntimeError,'Full research disabled'):
                require_execution_ready()

    def test_streaming_products_preserve_each_risk_choice(self):
        model={'id':'fixture','blocks':[{'risk':[50,100],'stop':[1,2]}]}
        self.assertEqual(len(list(configs(model))),4)


if __name__=='__main__':
    unittest.main()
