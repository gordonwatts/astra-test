# ASTRA jet-pT demonstration

This is a runnable ASTRA example using offline synthetic data: q2 (all jets)
and q3 (jets with strict `abs(eta) < 1`) from the
[IRIS-HEP benchmark questions](https://github.com/gordonwatts/iris-hep-llm-performance/blob/caab98db87b95790cb6a7df7978dfc221cf230f9/iris-hep-llm-questions.yaml).
It demonstrates the analysis record, two universe files, command-line
inspection, and executable recipes. In the benchmark, q1 is the missing-energy
question; it is not part of this comparison.

All data are synthetic. No ATLAS data download or ServiceX account is required.
The environment, caches, and generated results stay inside the cloned project
directory and are excluded from version control.

## Run it

With Git and [uv](https://docs.astral.sh/uv/getting-started/installation/)
installed, clone and run from PowerShell:

```powershell
git clone https://github.com/gordonwatts/astra-test.git
Set-Location astra-test
.\demo.ps1 -Setup
```

Setup creates a local Python 3.12 environment and installs the hashed dependency
lock. uv can download Python 3.12 if it is not already installed. Subsequent
runs use the existing environment:

```powershell
.\demo.ps1
```

The first setup needs package-download access; subsequent analysis runs make no
ServiceX, Rucio, or other network requests. This workflow has been tested on
Windows with Python 3.12. The wrapper keeps caches in this folder and sets
`PYTHONUTF8=1` so ASTRA's symbols work in captured Windows output.

The command shows `astra info` and `astra viz`, validates the analysis and both
universes, then executes the recipes declared in `astra.yaml`. It produces:

```text
results/
  q2_all_jets/
    jet_sample.json       # synthetic event-by-event jet arrays
    plot_1.png            # all jets, explicitly labelled SYNTHETIC
    jet_metrics.json      # raw-value mean and entries per event
    local-run.json        # commands and SHA-256 hashes from this local helper
  q3_central_jets/
    jet_sample.json       # identical content to the q2 sample
    plot_1.png            # jets passing abs(eta)<1
    jet_metrics.json
    local-run.json
```

Runs overwrite these generated files. `results/` is ignored by version control.

## Inspect the record without running the analysis

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\astra.exe validate
.\.venv\Scripts\astra.exe info
.\.venv\Scripts\astra.exe viz
.\.venv\Scripts\astra.exe viz --format mermaid
.\.venv\Scripts\astra.exe universe check universes/q2-all-jets.yaml
.\.venv\Scripts\python.exe run_demo.py --dry-run
```

`astra viz` shows the decision and its options. It does not draw the output
dependency graph. `run_demo.py --dry-run` validates and prints the expanded
recipe commands without generating artifacts.

Run just one universe or run the checks:

```powershell
.\.venv\Scripts\python.exe run_demo.py --universe universes/q3-central-jets.yaml
.\.venv\Scripts\python.exe -m unittest -v test_demo
```

## What each file does

| File | Purpose |
| --- | --- |
| `astra.yaml` | Inputs, outputs, their dependencies, the jet-acceptance decision, and executable recipe templates. |
| `universes/q2-all-jets.yaml` | Selects `jet_acceptance: all_jets`. |
| `universes/q3-central-jets.yaml` | Selects `jet_acceptance: central_jets`. |
| `config/servicex-request.yaml` | Records the intended Rucio DID, `n_files: 1`, unknown real file, and fixed mock settings. |
| `config/plot.yaml` | Identical display bins and range for the two plots. |
| `script.py` | Single-file Typer CLI implementing `fetch`, `plot`, and `metrics`, with PEP 723 dependency metadata. |
| `requirements.txt` | Full dependency lock, with versions and download hashes, generated from `script.py`. |
| `run_demo.py` | Small local helper that substitutes ASTRA placeholders and runs this example's recipes. |
| `demo.ps1` | Setup and demonstration command for Windows. |
| `test_demo.py` | Tests strict cut boundaries, event accounting, overflow, metrics, plotting, and the mock-only boundary. |

The installed CLI is **astra-tools 0.2.18** and its schema package is
**astra-spec 0.0.14**. The root `version: "0.0.14"` names the schema version,
not the CLI package version. The installed validator requires this field even
though the online format-reference table currently labels it optional.

## How the YAML and code connect

The analysis has one decision and three outputs:

```text
ServiceX request + script + environment lock
                   |
                   v
               jet_sample
                 /     \
                v       v
        jet_pt_plot    jet_metrics
             ^             ^
             +-- jet_acceptance --+
```

The two universes select an **option ID**, not a numeric threshold. For example,
the plot recipe contains:

```yaml
command: >-
  python {inputs.analysis_code} plot
  --jets {inputs.jet_sample} --acceptance {decisions.jet_acceptance}
  --settings {inputs.plot_settings} --out {output}
```

The local helper binds `inputs.jet_sample` to the generated JSON, substitutes
`all_jets` or `central_jets`, and assigns the destination `plot_1.png`. The script
maps `central_jets` to the strict object cut `abs(jets.eta) < 1.0`. ASTRA declares
the choice; the Python code implements its meaning. Code, plot configuration,
and the environment lock are declared as inputs because they affect outputs.

`jet_sample` has no acceptance decision, so both universes consume identical
synthetic content. This simple helper regenerates it in each result directory;
it does not cache or deduplicate outputs across universes.

## What is real and what is mocked

`fetch` calls `mock_delivery`, which generates a fixed-seed event sample with
aligned jagged `jet_pt` and `jet_eta` arrays. Momenta are already in GeV. A few
explicit fixtures include an empty event, jets exactly at eta = -1 and +1, an
event with no central jets, and a 400-GeV jet outside the plot range.

The selections, histogram filling, plots, and metrics actually execute. Neither
the mock event distribution nor its numerical results describe ATLAS data.
There is no ServiceX client or authentication dependency in this environment.
Changing `provider` to anything other than `mock` raises an error.

The full fixture gives these **synthetic** results:

| Universe | Events | Jet entries | Entries/event | Mean pT [GeV] |
| --- | ---: | ---: | ---: | ---: |
| q2 all jets | 500 | 3050 | 6.100 | 49.7584709253 |
| q3 central jets | 500 | 1079 | 2.158 | 50.8674893696 |

Each plot command prints one `METRIC: avg_entries_per_event=... mean=...` line.
The mean comes from the raw selected values, including overflow; entries/event
uses all 500 events, including those with no selected jets. There are no weights
or additional event or pT selections. Empty selections have a JSON `null` mean.

To connect ServiceX later, replace the provider with a PHYSLITE query using two
top-level selections: gather jets, then return a flat dictionary of `jet_pt`
and `jet_eta` arrays. Convert pT from MeV to GeV in that query. Deliver once with
`dataset.Rucio(the_recorded_DID)` and `NFiles=1`, and adapt the delivered file to
the event/column contract above. Fetch all jets once so both configurations can
use the same file. Record that actual file's identity and checksum, install
release-matched ServiceX dependencies, update the lock, and extend the current
synthetic-only input checks and labels before a real-data run. No live adapter
has been implemented or tested in this exercise.

## Assessment and limits

- **Fidelity:** the requested jet-level q2/q3 selections, unweighted fills,
  raw-value metrics, and retained zero-entry events are implemented. The
  benchmark's requirement to process one actual dataset file remains unmet
  deliberately; `n_files: 1` records the intended request only.
- **Clarity:** one spec and two small universe files expose the only choice;
  the shared intermediate exposes the common input. For two plots this adds
  bookkeeping, but the inputs and command bindings are easy to inspect.
- **Unknowns:** the real file, its availability, and numerical agreement with
  the benchmark references are unverified. `real_input_file: null` keeps this
  explicit. The toy generator was not tuned to those references.
- **Validation limits:** ASTRA checks structure, references, and recipe
  placeholders. It does not establish the semantics of `central_jets`, check
  the code's units, confirm dataset access, or prove physics correctness. The
  six implementation tests check the local selection and plotting behavior.

`astra` validates and inspects the record; it does not execute recipes. This
example uses `run_demo.py` to keep the Windows demonstration self-contained.
It supports this flat spec in declared dependency order, always reruns the
recipes, and uses `subprocess` without a shell. It is not a general ASTRA engine
and does not implement sub-analyses, conditional elements, scheduling,
container execution, or Lightcone's provenance guarantees. `local-run.json`
is an ordinary local audit record, not an `lc` manifest.

A later Lightcone demonstration would add its uv project and git/git-annex
setup and use the supported `lc` execution workflow. That has not been tested
here. The q6 and CalRatio try-outs are also left for later work.

## Sources consulted

- [Benchmark questions at caab98d](https://github.com/gordonwatts/iris-hep-llm-performance/blob/caab98db87b95790cb6a7df7978dfc221cf230f9/iris-hep-llm-questions.yaml).
- [ASTRA format reference](https://astra-spec.org/latest/specification/) and
  [CLI reference](https://astra-spec.org/latest/cli/), checked against the installed CLI.
- [Lightcone concepts](https://docs.lightconeresearch.org/user/concepts/).
- IRIS-HEP marketplace guidance at commit `288a2fd6859bb69975d9f8ea86da135a0857c892`:
  [ServiceX](https://github.com/iris-hep/marketplace/blob/288a2fd6859bb69975d9f8ea86da135a0857c892/iris-hep/skills/servicex/SKILL.md),
  [Awkward Array](https://github.com/iris-hep/marketplace/blob/288a2fd6859bb69975d9f8ea86da135a0857c892/iris-hep/skills/awkward-array/SKILL.md),
  [Hist](https://github.com/iris-hep/marketplace/blob/288a2fd6859bb69975d9f8ea86da135a0857c892/iris-hep/skills/hist/SKILL.md), and
  [standalone scripts](https://github.com/iris-hep/marketplace/blob/288a2fd6859bb69975d9f8ea86da135a0857c892/iris-hep/skills/standalone-script/SKILL.md).

To refresh the dependency lock after intentionally changing the script metadata:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
uv pip compile script.py --python .venv\Scripts\python.exe --generate-hashes --output-file requirements.txt
.\demo.ps1 -Setup
```
