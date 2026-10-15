import unittest
from purple_dragon_agent.runner import summarize_tests

class TestSummaryTests(unittest.TestCase):
    def result(self,text,exit_code=0,state='finished',truncated=False):return summarize_tests({'output':text,'exit_code':exit_code,'state':state,'truncated':truncated})
    def test_unittest_failure_counts_and_identifiers(self):
        r=self.result('FAIL: test_add (test_main.Tests)\nERROR: test_read (test_main.Tests)\nRan 4 tests in 0.02s\nFAILED (failures=1, errors=1, skipped=1)',1)
        self.assertEqual(r['outcome'],'failed');self.assertEqual(r['counts']['run'],4);self.assertEqual(r['counts']['failed'],1);self.assertEqual(r['counts']['errors'],1);self.assertEqual(len(r['failures']),2)
    def test_pytest_counts_ansi_and_failure_list(self):
        r=self.result('collected 3 items\nFAILED tests/test_add.py::test_add - AssertionError\n\x1b[31m=== 1 failed, 1 passed, 1 skipped in 0.20s ===\x1b[0m',1)
        self.assertEqual(r['counts']['collected'],3);self.assertEqual(r['counts']['passed'],1);self.assertEqual(r['counts']['skipped'],1);self.assertIn('tests/test_add.py',r['failures'][0])
    def test_no_tests_and_unrecognized_success_not_pass(self):
        self.assertEqual(self.result('Ran 0 tests in 0.00s\nOK')['outcome'],'no_tests')
        self.assertEqual(self.result('no tests ran in 0.1s',5)['outcome'],'no_tests')
        self.assertEqual(self.result('custom output')['outcome'],'unverified')
    def test_cancel_timeout_and_truncation_not_pass(self):
        for state,outcome in [('cancelled','cancelled'),('timed_out','timed_out'),('output_incomplete','incomplete')]:
            self.assertEqual(self.result('Ran 2 tests in 0.1s\nOK',state=state)['outcome'],outcome)
        self.assertEqual(self.result('Ran 2 tests in 0.1s\nOK',truncated=True)['outcome'],'incomplete')
    def test_failure_list_bounded_and_collection_error(self):
        r=self.result('\n'.join('ERROR: test_'+str(i) for i in range(30)),1)
        self.assertEqual(len(r['failures']),20);self.assertTrue(r['failure_list_truncated'])
        self.assertEqual(self.result('collected 0 items / 1 error\n1 error in 0.1s',2)['outcome'],'failed')
    def test_oversized_count_does_not_crash_summary(self):
        r=self.result('Ran '+('9'*5000)+' tests in 0.1s\nOK')
        self.assertIsNone(r['counts']['run']);self.assertEqual(r['outcome'],'unverified')
