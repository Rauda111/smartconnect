import importlib.util, unittest
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('operator_sc',Path(__file__).with_name('jury_operator.py'))
op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
class SafetyTests(unittest.TestCase):
    def test_no_approval_no_activity(self):
        with patch.object(op,'credentials',side_effect=AssertionError('credentials touched')),patch.object(op,'get',side_effect=AssertionError('HTTP touched')),patch.object(op,'save',side_effect=AssertionError('file touched')):
            with self.assertRaisesRegex(ValueError,'approval'):op.collect(False)
    def test_budget_initial_capped(self):self.assertEqual(op.remaining_budget(360),270)
    def test_budget_late_join(self):self.assertEqual(op.remaining_budget(310),247)
    def test_response_time_deducted(self):self.assertEqual(op.remaining_budget(310,7),240)
    def test_expired_shared_budget(self):self.assertEqual(op.remaining_budget(60),0)
    def test_no_extended_room_lease(self):
        for value in [361,0,-1,True,'300',float('nan')]:
            with self.assertRaises(ValueError):op.remaining_budget(value)
    def test_no_unknown_http_path(self):
        with self.assertRaises(ValueError):op.get('/join')
    def test_offline_check_does_not_http(self):
        with patch.object(op,'credentials',return_value={}),patch.object(op,'interface_status',return_value={'en0':True,'en6':True}),patch.object(op,'get',side_effect=AssertionError('HTTP touched')),patch.object(op,'save'),patch('builtins.print'):
            op.check(False)
if __name__=='__main__':unittest.main()
