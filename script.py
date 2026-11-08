#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "astra-tools==0.2.18",
#   "awkward==2.14.0",
#   "hist==2.12.1",
#   "matplotlib==3.11.2",
#   "mplhep==1.3.3",
#   "numpy==2.5.4",
#   "pyyaml==6.0.3",
#   "typer==0.27.3",
# ]
# ///
"""Offline q2/q3 example. There is deliberately no live ServiceX implementation."""

from enum import Enum
import json
import os
from pathlib import Path
from typing import Annotated

import awkward as ak
import numpy as np
import typer
import yaml

app = typer.Typer(add_completion=False, help=__doc__)


class Acceptance(str, Enum):
    all_jets = "all_jets"
    central_jets = "central_jets"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def mock_delivery(request: dict) -> dict:
    """ServiceX boundary: replace this provider, keeping the event/column contract."""
    if request["provider"] != "mock":
        raise ValueError("Only provider: mock is implemented; no remote requests are made.")
    if request["n_files"] != 1:
        raise ValueError("This demonstration models one input file only.")
    if request["columns"] != {"jet_pt": "GeV", "jet_eta": "dimensionless"}:
        raise ValueError("Expected jet_pt in GeV and dimensionless jet_eta.")
    settings = request["mock"]
    if settings["n_events"] < 4:
        raise ValueError("At least four events are needed for the boundary fixtures.")
    # Explicit cases: empty event, strict eta boundary, no central jets, overflow.
    pt = [[], [10., 20., 30., 40., 50.], [60., 70.], [400.]]
    eta = [[], [-1., -0.999, 0., 0.999, 1.], [-2., 2.], [0.]]
    rng = np.random.default_rng(settings["seed"])
    for _ in range(settings["n_events"] - len(pt)):
        size = int(rng.poisson(6.0))
        pt.append((15.0 + rng.exponential(35.0, size)).tolist())
        eta.append(rng.uniform(-2.8, 2.8, size).tolist())
    return {
        "synthetic": True,
        "intended_dataset": request["intended_dataset"],
        "real_input_file": None,
        "mock_file_id": settings["file_id"],
        "seed": settings["seed"],
        "units": request["columns"],
        "events": {"jet_pt": pt, "jet_eta": eta},
    }


def selected_values(sample: dict, acceptance: Acceptance) -> tuple[np.ndarray, int]:
    if not sample["synthetic"]:
        raise ValueError("This demo currently accepts explicitly synthetic input only.")
    if sample["units"] != {"jet_pt": "GeV", "jet_eta": "dimensionless"}:
        raise ValueError("Unexpected input units.")
    events = ak.Array(sample["events"])
    if not ak.all(ak.num(events.jet_pt, axis=1) == ak.num(events.jet_eta, axis=1)):
        raise ValueError("Jet pT and eta must be aligned within every event.")
    jets = ak.zip({"pt": events.jet_pt, "eta": events.jet_eta})
    if acceptance == Acceptance.central_jets:
        jets = jets[abs(jets.eta) < 1.0]
    # No event filter: events with zero selected jets remain in len(events).
    values = ak.to_numpy(ak.flatten(jets.pt, axis=1))
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("Jet pT values must be finite and nonnegative.")
    if not bool(ak.all(np.isfinite(events.jet_eta))):
        raise ValueError("Jet eta values must be finite.")
    return values, len(events)


def raw_metrics(values: np.ndarray, n_events: int, acceptance: Acceptance) -> dict:
    """Use the raw fills, never histogram-derived approximations to the mean."""
    return {
        "synthetic": True,
        "acceptance": acceptance.value,
        "n_events": n_events,
        "n_entries": len(values),
        "avg_entries_per_event": len(values) / n_events if n_events else None,
        "mean": float(np.mean(values)) if len(values) else None,
        "mean_unit": "GeV",
        "weights": "none",
    }


@app.command()
def fetch(
    request: Annotated[Path, typer.Option(exists=True)],
    out: Annotated[Path, typer.Option()],
) -> None:
    """Write a synthetic ServiceX-shaped delivery; never contact a service."""
    delivery = mock_delivery(yaml.safe_load(request.read_text(encoding="utf-8")))
    write_json(out, delivery)
    typer.echo(f"SYNTHETIC delivery: {len(delivery['events']['jet_pt'])} events -> {out}")


@app.command()
def metrics(
    jets: Annotated[Path, typer.Option(exists=True)],
    acceptance: Annotated[Acceptance, typer.Option()],
    out: Annotated[Path, typer.Option()],
) -> None:
    """Save synthetic unweighted raw-value metrics as JSON."""
    sample = json.loads(jets.read_text(encoding="utf-8"))
    values, n_events = selected_values(sample, acceptance)
    write_json(out, raw_metrics(values, n_events, acceptance))


@app.command()
def plot(
    jets: Annotated[Path, typer.Option(exists=True)],
    acceptance: Annotated[Acceptance, typer.Option()],
    settings: Annotated[Path, typer.Option(exists=True)],
    out: Annotated[Path, typer.Option()],
) -> None:
    """Plot the selected jets and print the benchmark-format metric line."""
    # Keep matplotlib's writable cache beside this code rather than in the document folder.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import hist
    import mplhep as hep

    sample = json.loads(jets.read_text(encoding="utf-8"))
    values, n_events = selected_values(sample, acceptance)
    result = raw_metrics(values, n_events, acceptance)
    cfg = yaml.safe_load(settings.read_text(encoding="utf-8"))
    plt.style.use(hep.style.ATLAS)
    h = hist.Hist.new.Reg(cfg["bins"], cfg["low"], cfg["high"], name="pt",
                         label=cfg["x_label"]).Int64()
    h.fill(pt=values)
    fig, ax = plt.subplots()
    h.plot1d(ax=ax, histtype="step", yerr=False, w2method="sqrt",
             color="tab:blue", linewidth=1.5)
    ax.set_ylabel(cfg["y_label"])
    title = "All jets (q2)" if acceptance == Acceptance.all_jets else r"Jets with $|\eta|<1$ (q3)"
    ax.set_title(title)
    ax.text(0.97, 0.95, "SYNTHETIC DATA\nOffline demonstration", transform=ax.transAxes,
            ha="right", va="top", fontsize=12, color="darkred")
    underflow = int(np.count_nonzero(values < cfg["low"]))
    overflow = int(np.count_nonzero(values >= cfg["high"]))
    fig.text(0.15, 0.02, f"{n_events} events; {len(values)} jets; underflow={underflow}, overflow={overflow}",
             fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    avg = result["avg_entries_per_event"]
    mean = result["mean"]
    typer.echo(f"METRIC: avg_entries_per_event={avg if avg is not None else 'nan'} "
               f"mean={mean if mean is not None else 'nan'}")


if __name__ == "__main__":
    app()
