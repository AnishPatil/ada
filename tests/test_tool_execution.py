"""Offline regression tests; no model requests or XFOIL processes are started."""

import contextlib
import io
import json
from types import SimpleNamespace
import unittest

from ada.ui.tool_execution import execute_batch, run_tool_loop, XFOIL


def tool(name, call_id, **arguments):
    return SimpleNamespace(type="function_call", name=name, call_id=call_id,
                           arguments=json.dumps(arguments))


class ToolExecutionTests(unittest.TestCase):
    def setUp(self):
        self.ui = SimpleNamespace(geometryItems=[], analysisItems={}, dataItems=[],
                                  activeGeometry=None, activeAnalysis=None, activeDataItems=None)
        self.executed = []

        def generate(**args):
            self.executed.append(("generate", dict(args)))
            self.ui.geometryItems.append(object())
            self.ui.activeGeometry = len(self.ui.geometryItems) - 1
            return "Query task complete"

        def add_case(**args):
            self.executed.append(("case", dict(args)))
            cases = self.ui.analysisItems.setdefault("xfoil", [])
            cases.append(SimpleNamespace(geometryIndex=self.ui.activeGeometry))
            self.ui.activeAnalysis = ("xfoil", len(cases) - 1)
            return "Query task complete"

        def run(**args):
            self.executed.append(("run", dict(args)))
            self.ui.dataItems.append({"geometry": args["geometryIndex"], "case": args["caseIndex"]})
            self.ui.activeDataItems = (self.ui.activeDataItems or []) + [len(self.ui.dataItems) - 1]
            return "Query task complete"

        def modify(**args):
            self.executed.append(("modify", dict(args)))
            return "Modified geometry"

        def plot(**args):
            self.executed.append(("plot", dict(args)))
            return "<img>plot</img>"

        self.handles = {"generateAirfoil": generate, XFOIL + "addAnalysisCase": add_case,
                        "run": run, "modifyGeometry": modify, XFOIL + "standardPlot": plot,
                        XFOIL + "modifyAnalysisCase": modify}
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def batch(self, items, cache=None, remaining=100):
        return execute_batch(self.ui, items, self.handles, "test", 8000,
                             cache if cache is not None else {}, 1, remaining)

    def workflow(self):
        return [tool("generateAirfoil", "g", aflString="NACA2412"),
                tool(XFOIL + "addAnalysisCase", "c"), tool("run", "r")]

    def test_all_calls_in_order(self):
        records, count = self.batch(self.workflow())
        self.assertEqual([x[0] for x in self.executed], ["generate", "case", "run"])
        self.assertEqual(count, 3)
        self.assertEqual([r["status"] for r in records], ["succeeded"] * 3)
        self.assertEqual(records[2]["effective_arguments"],
                         {"toolName": "xfoil", "caseIndex": "1", "geometryIndex": "1"})
        self.assertEqual(self.ui.analysisItems["xfoil"][0].geometryIndex, 0)

    def test_reverse_order_waits_for_prerequisites(self):
        records, _ = self.batch(list(reversed(self.workflow())))
        self.assertEqual([x[0] for x in self.executed], ["generate", "case", "run"])
        self.assertEqual([r["execution_order"] for r in records], [3, 2, 1])

    def test_new_objects_used_instead_of_old_active_objects(self):
        self.batch(self.workflow())
        self.executed.clear()
        records, _ = self.batch(list(reversed(self.workflow())))
        self.assertEqual(records[0]["effective_arguments"]["geometryIndex"], "2")
        self.assertEqual(records[0]["effective_arguments"]["caseIndex"], "2")

    def test_explicit_existing_ids_are_honored(self):
        self.batch(self.workflow())
        self.executed.clear()
        items = self.workflow()
        items[-1] = tool("run", "r2", geometryIndex="1", caseIndex="1", toolName="xfoil")
        records, _ = self.batch(items)
        self.assertEqual(records[-1]["effective_arguments"]["geometryIndex"], "1")
        self.assertEqual(records[-1]["effective_arguments"]["caseIndex"], "1")
        self.assertEqual(self.ui.activeGeometry, 0)

    def test_eight_coefficient_calls_are_not_deduplicated_by_name(self):
        items = [self.workflow()[0]] + [
            tool("modifyGeometry", f"m{i}", surface="upper", index=str(i),
                 value=str(i / 100), geometryIndex="None") for i in range(1, 9)]
        records, count = self.batch(items)
        self.assertEqual(count, 9)
        self.assertEqual([x[1]["index"] for x in self.executed[1:]], list(map(str, range(1, 9))))
        self.assertTrue(all(r["status"] == "succeeded" for r in records))

    def test_failed_creator_blocks_dependents_even_if_old_objects_exist(self):
        self.batch(self.workflow())
        self.executed.clear()
        self.handles["generateAirfoil"] = lambda **kwargs: "Error: invalid naca4"
        records, _ = self.batch(self.workflow())
        self.assertEqual([r["status"] for r in records], ["failed", "skipped", "skipped"])
        self.assertEqual(self.executed, [])

    def test_independent_call_runs_after_failure(self):
        bad = tool("generateAirfoil", "bad")
        bad.arguments = "not JSON"
        records, count = self.batch([bad, tool("generateAirfoil", "good", aflString="NACA0012")])
        self.assertEqual([r["status"] for r in records], ["failed", "succeeded"])
        self.assertEqual(count, 1)

    def test_unknown_tool_is_not_silently_dropped(self):
        records, _ = self.batch([tool("missing", "m"), self.workflow()[0]])
        self.assertEqual([r["status"] for r in records], ["failed", "succeeded"])

    def test_exception_blocks_dependents(self):
        def fail(**kwargs):
            raise RuntimeError("solver failed")
        self.handles["run"] = fail
        records, _ = self.batch(self.workflow() + [tool(XFOIL + "standardPlot", "p")])
        self.assertEqual(records[-2]["status"], "failed")
        self.assertEqual(records[-1]["status"], "skipped")

    def test_plot_uses_new_run_data_not_old_selection(self):
        self.batch(self.workflow())
        self.executed.clear()
        items = [tool(XFOIL + "standardPlot", "p")] + list(reversed(self.workflow()))
        records, _ = self.batch(items)
        self.assertEqual([x[0] for x in self.executed], ["generate", "case", "run", "plot"])
        self.assertEqual(records[0]["effective_arguments"]["dataIndicies"], "[2]")

    def test_explicit_future_index_resolves_after_creation(self):
        items = self.workflow()
        items[-1] = tool("run", "r", toolName="xfoil", caseIndex="1", geometryIndex="1")
        records, _ = self.batch(list(reversed(items)))
        self.assertTrue(all(r["status"] == "succeeded" for r in records))

    def test_invalid_explicit_index_does_not_fall_back_to_active(self):
        self.batch(self.workflow())
        records, count = self.batch([tool("run", "r", geometryIndex="999")])
        self.assertEqual(records[0]["status"], "failed")
        self.assertEqual(count, 0)

    def test_explicit_old_resources_can_run_after_unrelated_creation_fails(self):
        self.batch(self.workflow())
        self.handles["generateAirfoil"] = lambda **kwargs: "FAILURE: bad airfoil"
        records, _ = self.batch([
            tool("generateAirfoil", "new"),
            tool("run", "old", geometryIndex="1", caseIndex="1", toolName="xfoil"),
        ])
        self.assertEqual([r["status"] for r in records], ["failed", "succeeded"])

    def test_non_object_arguments_do_not_execute_with_defaults(self):
        item = tool("generateAirfoil", "g")
        item.arguments = "[]"
        records, count = self.batch([item])
        self.assertEqual(records[0]["status"], "failed")
        self.assertEqual(count, 0)

    def test_standalone_case_creation_does_not_require_geometry(self):
        records, count = self.batch([self.workflow()[1]])
        self.assertEqual(count, 1)
        self.assertEqual(records[0]["status"], "succeeded")

    def test_duplicate_call_ids_are_executed_only_once(self):
        cache = {}
        self.batch([self.workflow()[0]], cache)
        records, count = self.batch([self.workflow()[0]], cache)
        self.assertEqual(count, 0)
        self.assertEqual(records[0]["status"], "reused")
        self.assertEqual(len(self.ui.geometryItems), 1)

    def test_changed_arguments_with_duplicate_id_are_rejected(self):
        cache = {}
        self.batch([self.workflow()[0]], cache)
        records, _ = self.batch([tool("generateAirfoil", "g", aflString="different")], cache)
        self.assertEqual(records[0]["status"], "failed")

    def test_ambiguous_forward_reference_reports_failure(self):
        items = [tool("modifyGeometry", "m", geometryIndex="None"),
                 tool("generateAirfoil", "g1"), tool("generateAirfoil", "g2")]
        records, _ = self.batch(items)
        self.assertEqual(records[0]["status"], "failed")
        self.assertIn("Ambiguous", records[0]["result"])
        self.assertEqual(len(self.ui.geometryItems), 2)

    def test_execution_limit_records_unexecuted_calls(self):
        records, count = self.batch(self.workflow(), remaining=1)
        self.assertEqual(count, 1)
        self.assertEqual([r["status"] for r in records], ["succeeded", "skipped", "skipped"])

    def test_full_loop_reports_every_result_to_model(self):
        prompts = []
        responses = iter([SimpleNamespace(output=self.workflow(), output_text="", model="test"),
                          SimpleNamespace(output=[], output_text="Finished", model="test")])
        def send(prompt, data):
            prompts.append(prompt)
            return next(responses)
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "Make an airfoil and run it", [], self.handles,
                      send, 8000, "test")
        self.assertEqual(len(call.tool_results), 3)
        self.assertEqual(call.response, "Finished")
        for call_id in ("g", "c", "r"):
            self.assertIn(f'"call_id": "{call_id}"', prompts[1])
        self.assertIn('"geometryIndex": 1', prompts[1])

    def test_text_only_response_is_saved(self):
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        response = {"output": [], "output_text": "What speed?", "status": "completed"}
        run_tool_loop(self.ui, call, "test", [], self.handles,
                      lambda *args: response, 8000, "test")
        self.assertEqual(call.response, "What speed?")
        self.assertEqual(call.tool_calls, [])

    def test_later_success_text_does_not_hide_tool_failure(self):
        self.handles["generateAirfoil"] = lambda **kwargs: "FAILURE: airfoil not found"
        responses = iter([{"output": self.workflow()}, {"output": [], "output_text": "Done"}])
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "test", [], self.handles,
                      lambda *args: next(responses), 8000, "test")
        self.assertIn("ERROR", call.response)
        self.assertEqual(len(call.tool_results), 3)

    def test_model_connection_error_preserves_completed_tool_records(self):
        def send(*args):
            if self.ui.geometryItems:
                raise RuntimeError("Connection lost")
            return {"output": [self.workflow()[0]]}
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "test", [], self.handles, send, 8000, "test")
        self.assertEqual(call.tool_results[0]["status"], "succeeded")
        self.assertIn("Connection lost", call.response)

    def test_message_content_is_saved_without_output_text_property(self):
        response = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": "Which airfoil?"}]}]}
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "test", [], self.handles, lambda *args: response, 8000, "test")
        self.assertEqual(call.response, "Which airfoil?")

    def test_incomplete_response_is_not_reported_as_success(self):
        response = {"output": [], "status": "incomplete", "incomplete_details": {"reason": "limit"}}
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "test", [], self.handles, lambda *args: response, 8000, "test")
        self.assertIn("ERROR", call.response)
        self.assertEqual(call.model_responses[0]["incomplete_details"], {"reason": "limit"})

    def test_plot_output_is_kept_with_final_model_text(self):
        responses = iter([{"output": self.workflow() + [tool(XFOIL + "standardPlot", "p")]},
                          {"output": [], "output_text": "Complete"}])
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "test", [], self.handles,
                      lambda *args: next(responses), 8000, "test")
        self.assertIn("<img>", call.response)
        self.assertIn("Complete", call.response)

    def test_model_loop_limit_is_visible(self):
        call = SimpleNamespace(tool_calls=[], response=None, interpretation=None)
        run_tool_loop(self.ui, call, "test", [], self.handles,
                      lambda *args: {"output": [self.workflow()[0]]}, 8000, "test", max_rounds=2)
        self.assertEqual(len(self.ui.geometryItems), 1)
        self.assertIn("ERROR", call.response)


if __name__ == "__main__":
    unittest.main()
