import unittest
from unittest.mock import patch
import app
class LanguageTests(unittest.TestCase):
    def test_thai_intent_and_financial_boundary(self):
        with patch.object(app.services,'select_runtime',side_effect=lambda d,o:d):
            for text,mode in [('ช่วยอธิบายฟังก์ชันนี้','chat'),('ทำไมโปรแกรมถึงช้า','chat'),('ช่วยแก้ไขบั๊กในโปรแกรม','job'),('เขียนฟังก์ชัน greeting','job')]:self.assertEqual(app.route(text)['mode'],mode)
            self.assertIn('blocked_reason',app.route('ช่วยโอนเงิน'))
    def test_classifier_can_abstain_without_escalating(self):
        with patch.object(app,'local_call',return_value='{"mode":"abstain"}'),patch.object(app.services,'select_runtime') as select:
            with self.assertRaisesRegex(ValueError,'uncertain'):app.route('hmm maybe do something')
            select.assert_not_called()
