"""Execute this flat ASTRA example's recipes locally, without Lightcone."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    # ASTRA's check marks need UTF-8 when stdout is captured on Windows.
    os.environ["PYTHONUTF8"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, help="Run just this universe (default: both).")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print commands only.")
    args = parser.parse_args()
    astra = Path(sys.executable).with_name("astra.exe" if os.name == "nt" else "astra")
    subprocess.run([str(astra), "validate"], cwd=ROOT, check=True)
    spec_path = ROOT / "astra.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    universes = [args.universe] if args.universe else sorted((ROOT / "universes").glob("*.yaml"))
    for universe_path in universes:
        universe_path = ROOT / universe_path
        subprocess.run([str(astra), "validate", str(universe_path), "-a", str(spec_path)],
                       cwd=ROOT, check=True)
        universe = yaml.safe_load(universe_path.read_text(encoding="utf-8"))
        # No conditions/sub-analyses are implemented here. This helper is intentionally
        # limited to this example; astra-tools validates the record, not this runner.
        result_dir = ROOT / "results" / universe["id"]
        artifacts = {i["id"]: ROOT / i["source"] for i in spec["inputs"]}
        records = []
        for output in spec["outputs"]:
            filename = "plot_1.png" if output["id"] == "jet_pt_plot" else f"{output['id']}.{output['format']}"
            target = result_dir / filename
            dependencies = {i: artifacts[i] for i in output["inputs"]}
            bindings = {
                "inputs": SimpleNamespace(**{key: str(value) for key, value in dependencies.items()}),
                "decisions": SimpleNamespace(**universe["decisions"]),
                "output": str(target),
            }
            # Tokenize BEFORE substitution so a bound path with spaces stays one argument.
            command = [token.format_map(bindings) for token in shlex.split(output["recipe"]["command"])]
            if command[0] != "python":
                raise ValueError("This helper supports only Python recipes for this demo.")
            command[0] = sys.executable
            print(f"[{universe['id']}/{output['id']}] {shlex.join(command)}", flush=True)
            if not args.dry_run:
                subprocess.run(command, cwd=ROOT, check=True)
                if not target.is_file():
                    raise RuntimeError(f"Recipe did not create {target}")
                records.append({
                    "output": output["id"],
                    "artifact": str(target.relative_to(ROOT)),
                    "sha256": digest(target),
                    "argv": command,
                    "inputs_sha256": {key: digest(value) for key, value in dependencies.items()},
                })
            artifacts[output["id"]] = target
        if not args.dry_run:
            manifest = {
                "synthetic": True,
                "runner": "local demo helper; not lc and not certified provenance",
                "universe": universe["id"],
                "decisions": universe["decisions"],
                "python": sys.version,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "astra_sha256": digest(spec_path),
                "universe_sha256": digest(universe_path),
                "outputs": records,
            }
            (result_dir / "local-run.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
