"""Run the reproducible DDXPlus and disease-model workflow sequentially."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
LOG = logging.getLogger("run_all")


def run_python(script_name: str, *arguments: str) -> None:
    script = SCRIPT_DIR / script_name
    if not script.is_file():
        raise FileNotFoundError(f"Workflow step does not exist: {script}")
    command = [sys.executable, str(script), *arguments]
    LOG.info("Running: %s", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def run_powershell(script_name: str) -> None:
    executable = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        raise RuntimeError("PowerShell is required for the Figshare download step.")
    script = SCRIPT_DIR / script_name
    if not script.is_file():
        raise FileNotFoundError(f"Workflow step does not exist: {script}")
    subprocess.run(
        [
            executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the local API after data download, training, and evaluation finish.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    steps = [
        ("data inspection", lambda: run_python("01_inspect_data.py")),
        ("Figshare DDXPlus download and extraction", lambda: run_powershell("02_download_ddxplus.ps1")),
        ("symptoms model training", lambda: run_python("03_train_symptoms.py")),
        ("DDXPlus neural network training", lambda: run_python("04_train_ddxplus.py")),
        ("diabetes model training", lambda: run_python("05_train_diabetes.py")),
        ("heart model training", lambda: run_python("06_train_heart.py")),
        ("kidney model training", lambda: run_python("07_train_kidney.py")),
        ("new dataset training and evaluation", lambda: run_python("09_train_new_datasets.py")),
        ("all held-out evaluations", lambda: run_python("08_evaluate_all.py")),
    ]
    for label, action in steps:
        LOG.info("Starting %s", label)
        action()
        LOG.info("Completed %s", label)
    if args.serve:
        LOG.info("Starting API at http://%s:%d", args.host, args.port)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                args.host,
                "--port",
                str(args.port),
            ],
            cwd=ROOT,
            check=True,
        )
    LOG.info("All dataset steps completed.")


if __name__ == "__main__":
    main()
