"""Checks that ASTRA's declared q2/q3 semantics match the local implementation."""
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from typer.testing import CliRunner
import yaml

from script import Acceptance, app, mock_delivery, raw_metrics, selected_values

ROOT = Path(__file__).resolve().parent


class SelectionTests(unittest.TestCase):
    def setUp(self):
        request = yaml.safe_load((ROOT / "config/servicex-request.yaml").read_text())
        request["mock"]["n_events"] = 4
        self.sample = mock_delivery(request)

    def test_all_jets_keep_empty_events_and_overflow_in_metrics(self):
        values, n_events = selected_values(self.sample, Acceptance.all_jets)
        result = raw_metrics(values, n_events, Acceptance.all_jets)
        self.assertEqual(n_events, 4)
        self.assertEqual(result["n_entries"], 8)
        self.assertEqual(result["avg_entries_per_event"], 2.0)
        self.assertEqual(result["mean"], 85.0)  # includes the 400-GeV jet

    def test_central_cut_is_strict_and_is_not_an_event_cut(self):
        values, n_events = selected_values(self.sample, Acceptance.central_jets)
        np.testing.assert_array_equal(values, [20., 30., 40., 400.])
        result = raw_metrics(values, n_events, Acceptance.central_jets)
        self.assertEqual(n_events, 4)  # zero jets and zero passing jets both remain
        self.assertEqual(result["avg_entries_per_event"], 1.0)
        self.assertEqual(result["mean"], 122.5)

    def test_empty_selection_has_explicit_undefined_mean(self):
        self.sample["events"] = {"jet_pt": [[20.], []], "jet_eta": [[2.], []]}
        values, n_events = selected_values(self.sample, Acceptance.central_jets)
        result = raw_metrics(values, n_events, Acceptance.central_jets)
        self.assertEqual(result["avg_entries_per_event"], 0.0)
        self.assertIsNone(result["mean"])

    def test_no_live_provider_is_accepted(self):
        request = yaml.safe_load((ROOT / "config/servicex-request.yaml").read_text())
        request["provider"] = "servicex"
        with self.assertRaisesRegex(ValueError, "Only provider: mock"):
            mock_delivery(request)

    def test_plot_cli_reports_raw_metrics_and_creates_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "jets.json"
            out = Path(tmp) / "plot.png"
            data.write_text(json.dumps(self.sample))
            result = CliRunner().invoke(app, ["plot", "--jets", str(data), "--acceptance",
                "central_jets", "--settings", str(ROOT / "config/plot.yaml"), "--out", str(out)])
            self.assertEqual(result.exit_code, 0, result.output)
            lines = [line for line in result.output.splitlines() if line.startswith("METRIC:")]
            self.assertEqual(lines, ["METRIC: avg_entries_per_event=1.0 mean=122.5"])
            self.assertTrue(out.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_full_fixture_matches_independent_python_calculation(self):
        request = yaml.safe_load((ROOT / "config/servicex-request.yaml").read_text())
        sample = mock_delivery(request)
        self.assertEqual(sample, mock_delivery(request))
        events = sample["events"]
        for acceptance in Acceptance:
            expected = [pt for pts, etas in zip(events["jet_pt"], events["jet_eta"])
                        for pt, eta in zip(pts, etas)
                        if acceptance == Acceptance.all_jets or abs(eta) < 1.0]
            values, n_events = selected_values(sample, acceptance)
            result = raw_metrics(values, n_events, acceptance)
            self.assertEqual(result["n_entries"], len(expected))
            self.assertEqual(n_events, request["mock"]["n_events"])
            self.assertAlmostEqual(result["mean"], math.fsum(expected) / len(expected))


if __name__ == "__main__":
    unittest.main()
