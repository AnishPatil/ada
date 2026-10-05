"""Integration tests using ADA geometry/case tools with model and solver mocks."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("PATH_TO_ADA", str(Path(__file__).resolve().parents[1]) + os.sep)

from ada.ui.uiManager import UIHandler, LocalAPI, xfoilAPI


class UIToolLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ui = UIHandler.__new__(UIHandler)
        self.ui.sessionDirectory = self.temp.name
        self.ui.geometryItems = []
        self.ui.analysisItems = {}
        self.ui.dataItems = []
        self.ui.calls = []
        self.ui.activeGeometry = None
        self.ui.activeAnalysis = None
        self.ui.activeDataItems = None
        self.ui.graphicWindowDictionary = {}
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def response(self, calls):
        return SimpleNamespace(output=[SimpleNamespace(
            type="function_call", name=name, arguments=json.dumps(args), call_id=f"call_{i}"
        ) for i, (name, args) in enumerate(calls)], output_text="", model="offline-test")

    def invoke(self, calls):
        responses = [self.response(calls), SimpleNamespace(output=[], output_text="Complete.")]
        with patch("ada.ui.uiManager.sendToOpenAI", side_effect=responses), \
                patch("ada.ui.uiManager.resolve_model", return_value="offline-test"):
            self.ui.makeCall("Generate an airfoil and create an XFOIL case")
        return json.loads((Path(self.temp.name) / "Call_1" / "call_log.json").read_text())

    def test_generate_and_create_case_in_one_response(self):
        log = self.invoke([
            ("generateAirfoil", {"aflString": "NACA2412"}),
            ("analysis_apis_xfoil_addAnalysisCase", {}),
        ])
        self.assertEqual(len(self.ui.geometryItems), 1)
        self.assertEqual(len(self.ui.analysisItems["xfoil"]), 1)
        self.assertEqual(self.ui.analysisItems["xfoil"][0].geometryIndex, 0)
        self.assertEqual(len(log["tool_calls"]), 2)
        self.assertEqual([r["status"] for r in log["tool_results"]], ["succeeded"] * 2)

    def test_reversed_batch_uses_new_geometry_and_case_in_solver(self):
        received = []
        def solver(ui, toolName, caseIndex, geometryIndex, **kwargs):
            received.append((toolName, caseIndex, geometryIndex))
            self.assertEqual(len(ui.geometryItems), 1)
            self.assertEqual(len(ui.analysisItems["xfoil"]), 1)
            ui.dataItems.append({"geometryIndex": geometryIndex - 1})
            ui.activeDataItems = [0]
            return "Query task complete"
        with patch.object(xfoilAPI, "run", side_effect=solver):
            log = self.invoke([
                ("run", {"toolName": "xfoil", "geometryIndex": "None", "caseIndex": "None"}),
                ("analysis_apis_xfoil_addAnalysisCase", {}),
                ("generateAirfoil", {"aflString": "NACA2412"}),
            ])
        self.assertEqual(received, [("xfoil", 1, 1)])
        self.assertEqual([r["execution_order"] for r in log["tool_results"]], [3, 2, 1])

    def test_modify_geometry_honors_explicit_nonactive_index(self):
        api = LocalAPI()
        api.generateAirfoil(self.ui, "NACA2412")
        api.generateAirfoil(self.ui, "NACA0012")
        original_second = float(self.ui.geometryItems[1].upperCoefficients[0])
        api.modifyGeometry(self.ui, "upper", "K[1]", "0.3", "1")
        self.assertAlmostEqual(float(self.ui.geometryItems[0].upperCoefficients[0]), 0.3)
        self.assertAlmostEqual(float(self.ui.geometryItems[1].upperCoefficients[0]), original_second)

    def test_locked_geometry_is_copied_once_for_multiple_edits(self):
        api = LocalAPI()
        api.generateAirfoil(self.ui, "NACA2412")
        original = [float(v) for v in self.ui.geometryItems[0].upperCoefficients]
        self.ui.geometryItems[0].mutableLock = True
        log = self.invoke([
            ("modifyGeometry", {"geometryIndex": "None", "surface": "upper", "index": "1", "value": "0.3"}),
            ("modifyGeometry", {"geometryIndex": "None", "surface": "upper", "index": "2", "value": "0.4"}),
        ])
        self.assertEqual(len(self.ui.geometryItems), 2)
        self.assertEqual([float(v) for v in self.ui.geometryItems[0].upperCoefficients], original)
        self.assertAlmostEqual(float(self.ui.geometryItems[1].upperCoefficients[0]), 0.3)
        self.assertAlmostEqual(float(self.ui.geometryItems[1].upperCoefficients[1]), 0.4)
        self.assertEqual(log["tool_results"][1]["effective_arguments"]["geometryIndex"], "2")

    def test_text_only_reply_survives_session_serialization(self):
        response = SimpleNamespace(output=[], output_text="Which airfoil would you like?")
        with patch("ada.ui.uiManager.sendToOpenAI", return_value=response), \
                patch("ada.ui.uiManager.resolve_model", return_value="offline-test"):
            self.ui.makeCall("Make a good airfoil")
        log = json.loads((Path(self.temp.name) / "Call_1" / "call_log.json").read_text())
        self.assertEqual(log["response"], response.output_text)
        self.assertEqual(log["tool_calls"], [])


if __name__ == "__main__":
    unittest.main()
