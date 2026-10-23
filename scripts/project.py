"""Cross-platform BloodWatch project helper.

Usage:
    python scripts/project.py doctor
    python scripts/project.py setup
    python scripts/project.py run
    python scripts/project.py data
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


class ProjectError(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    process = subprocess.Popen(command, cwd=cwd, env=env)
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        # Ctrl+C is normally delivered to both processes because they share a
        # console/process group. Explicit cleanup also covers platforms or
        # timing windows where the child does not receive the interrupt.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    if returncode:
        raise ProjectError(f"Command failed with exit code {returncode}: {' '.join(command)}")


def python_supported() -> bool:
    return (3, 12) <= sys.version_info[:2] < (3, 16)


def doctor() -> bool:
    ok = True
    print("BloodWatch dependency check")
    print(f"Repository: {ROOT}")
    print(f"Operating system: {sys.platform}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    if not python_supported():
        ok = False
        print("  ERROR: Use Python 3.12 through 3.15; Python 3.14 or 3.15 is recommended.")
    else:
        print("  OK")

    if VENV_PYTHON.exists():
        print(f"Virtual environment: found at {VENV}")
        check = subprocess.run(
            [str(VENV_PYTHON), "-c", "import fastapi, scipy, uvicorn"],
            cwd=ROOT,
            check=False,
        )
        if check.returncode:
            ok = False
            print("  INCOMPLETE: run the setup command again.")
        else:
            print("  Python packages: OK")
    else:
        print("Virtual environment: not created yet")

    print("Result:", "READY" if ok else "ACTION REQUIRED")
    return ok


def setup() -> None:
    if not python_supported():
        raise ProjectError("Use Python 3.12 through 3.15; Python 3.14 or 3.15 is recommended.")
    if not VENV_PYTHON.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(ROOT / "app" / "requirements.txt")])
    run([str(VENV_PYTHON), str(ROOT / "scripts" / "generate_scenarios.py")])
    print("\nSetup complete. Run: python scripts/project.py run")


def require_setup() -> None:
    if not VENV_PYTHON.exists():
        raise ProjectError("Local Python environment is missing. Run the setup command first.")


def serve() -> None:
    require_setup()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "app")
    dashboard_url = "http://127.0.0.1:8000"
    print("Starting BloodWatch dashboard...", flush=True)
    server = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        env=environment,
    )
    simulator: subprocess.Popen | None = None
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise ProjectError(f"Dashboard server exited with code {server.returncode}.")
            try:
                with urlopen(f"{dashboard_url}/health", timeout=1):
                    break
            except (URLError, TimeoutError):
                time.sleep(0.25)
        else:
            raise ProjectError("Dashboard server did not become ready within 30 seconds.")

        print(f"Dashboard ready: {dashboard_url}", flush=True)
        print("Keep this terminal open. Press Ctrl+C to stop.", flush=True)
        print("Starting the simulated temperature feed.", flush=True)
        simulator_command = [
            str(VENV_PYTHON), str(ROOT / "scripts" / "stream_temperature.py"), "--interval", "15"
        ]
        simulator = subprocess.Popen(
            simulator_command,
            cwd=ROOT,
            env=environment,
        )
        while True:
            if server.poll() is not None:
                raise ProjectError(f"Dashboard server exited with code {server.returncode}.")
            if simulator.poll() is not None:
                raise ProjectError(f"Temperature simulator exited with code {simulator.returncode}.")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping dashboard and simulated temperature feed.", flush=True)
    finally:
        for process in (simulator, server):
            if process is not None and process.poll() is None:
                process.terminate()
        for process in (simulator, server):
            if process is not None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def generate_data() -> None:
    if not VENV_PYTHON.exists():
        raise ProjectError("Local Python environment is missing. Run the setup command first.")
    run([str(VENV_PYTHON), str(ROOT / "scripts" / "generate_scenarios.py")])


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up, check, or run BloodWatch on macOS and Windows.")
    parser.add_argument("action", choices=("doctor", "setup", "run", "data"))
    arguments = parser.parse_args()
    try:
        if arguments.action == "doctor":
            return 0 if doctor() else 1
        if arguments.action == "setup":
            setup()
        elif arguments.action == "run":
            serve()
        elif arguments.action == "data":
            generate_data()
    except KeyboardInterrupt:
        print("\nCancelled by user. You can safely rerun the command when ready.", file=sys.stderr)
        return 130
    except (ProjectError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
