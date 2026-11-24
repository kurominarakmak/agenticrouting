import unittest
from benchmarks.acceptance import final_answer,grounded_answer
class BenchmarkAcceptanceTests(unittest.TestCase):
 def test_only_final_visible_answer_counts(self):
  self.assertFalse(grounded_answer('<think>1000 hash</think>Unable to answer','1000',['hash']))
  self.assertFalse(grounded_answer('<think>1000 hash','1000',['hash']))
  self.assertFalse(grounded_answer('10000 hash','1000',['hash']))
  self.assertTrue(grounded_answer('<think>irrelevant</think>1,000 hash','1000',['hash']))
  self.assertEqual(final_answer('<think>private</think>visible'),'visible')
