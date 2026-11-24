import importlib.util
import unittest
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1]/"benchmarks"/"routing_eval.py"
spec=importlib.util.spec_from_file_location("routing_eval",MODULE)
routing_eval=importlib.util.module_from_spec(spec);spec.loader.exec_module(routing_eval)


class RoutingEvalScorerTests(unittest.TestCase):
    def test_strict_intent_scoring_keeps_invalid_labels_as_errors(self):
        rows=[{"expected_intent":"coding","actual_intent":"coding","latency_ms":10,"difficulty":3,"expected_difficulty":3,"observed_usage":{"calls":1,"input_tokens":9,"output_tokens":4}},
              {"expected_intent":"coding","actual_intent":"planned_work","latency_ms":20,"difficulty":5,"expected_difficulty":4,"error":"invalid intent","observed_usage":{"calls":0}}]
        result=routing_eval.score(rows)
        self.assertEqual(result["intent_correct"],1);self.assertEqual(result["valid_decisions"],1)
        self.assertEqual(result["errors"],1);self.assertEqual(result["observed_usage"],{"calls":1,"input_tokens":9,"output_tokens":4})
        self.assertIsNone(result["completion_metrics"]);self.assertEqual(result["execution_quality"],"not measured")

    def test_plans_are_replays_and_do_not_invent_completion_metrics(self):
        row={"id":"case","actual_intent":"coding","difficulty":4}
        result=routing_eval._decision_plans([row])
        self.assertEqual(result["fixed_native"]["rows"][0]["runtime"],"codex-chatgpt")
        self.assertEqual(result["hybrid"]["rows"][0]["roles"],["worker","reviewer"])
        self.assertTrue(result["fixed_native"]["replay_only"]);self.assertTrue(result["hybrid"]["replay_only"])
        self.assertIsNone(result["hybrid"]["rows"][0]["execution_quality"])
        self.assertIsNone(result["hybrid"]["rows"][0]["completion_metrics"])

    def test_report_is_a_valid_decision_and_context_case_abstains_without_provenance(self):
        case=next(x for x in routing_eval.CASES if x["id"]=="context_report")
        absent=routing_eval._case_for_context(case,False)
        present=routing_eval._case_for_context(case,True)
        self.assertEqual((absent["expected_intent"],absent["context_resolution"]),("clarify","unresolved"))
        self.assertEqual((present["expected_intent"],present["context_resolution"]),("report","resolved"))
        result=routing_eval.score([{"expected_intent":"report","actual_intent":"report","roles":["assistant"],
                                    "expected_roles":["assistant"],"context_resolution":"resolved",
                                    "expected_context_resolution":"resolved","observed_usage":{"calls":1}}])
        self.assertEqual(result["valid_decisions"],1);self.assertEqual(result["intent_accuracy"],1.0)
