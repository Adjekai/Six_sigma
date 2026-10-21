"""Cross-platform BloodWatch project helper.

Usage:
    python scripts/project.py doctor
    python scripts/project.py setup
    python scripts/project.py test
    python scripts/project.py run
    python scripts/project.py data
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
FRONTEND = ROOT / "app" / "frontend"


class ProjectError(RuntimeError):
    pass


def command_path(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ProjectError(f"Required command not found: {name}")
    return path


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode:
        raise ProjectError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def captured(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def python_supported() -> bool:
    return (3, 12) <= sys.version_info[:2] < (3, 16)


def node_supported(version: str) -> bool:
    numbers = version.lstrip("v").split(".")
    try:
        major, minor = int(numbers[0]), int(numbers[1])
    except (ValueError, IndexError):
        return False
    return (major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major > 22


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

    for tool in ("node", "npm"):
        path = shutil.which(tool)
        if not path:
            ok = False
            print(f"{tool}: NOT FOUND")
            continue
        version = captured([path, "--version"])
        print(f"{tool}: {version} ({path})")
        if tool == "node" and not node_supported(version):
            ok = False
            print("  ERROR: Vite requires Node 20.19+, Node 22.12+, or a newer major release.")

    if VENV_PYTHON.exists():
        print(f"Virtual environment: found at {VENV}")
        check = subprocess.run(
            [str(VENV_PYTHON), "-c", "import fastapi, scipy, uvicorn, pytest, httpx"],
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

    if (FRONTEND / "node_modules").is_dir():
        print("Frontend packages: found")
    else:
        print("Frontend packages: not installed yet")

    print("Result:", "READY" if ok else "ACTION REQUIRED")
    return ok


def setup() -> None:
    if not python_supported():
        raise ProjectError("Use Python 3.12 through 3.15; Python 3.14 or 3.15 is recommended.")
    npm = command_path("npm")
    node = command_path("node")
    node_version = captured([node, "--version"])
    if not node_supported(node_version):
        raise ProjectError("Vite requires Node 20.19+, Node 22.12+, or a newer major release.")

    if not VENV_PYTHON.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(ROOT / "app" / "requirements-dev.txt")])
    run([npm, "ci"], cwd=FRONTEND)
    run([str(VENV_PYTHON), str(ROOT / "scripts" / "generate_scenarios.py")])
    print("\nSetup complete. Run: python scripts/project.py run")


def require_setup() -> str:
    if not VENV_PYTHON.exists():
        raise ProjectError("Local Python environment is missing. Run the setup command first.")
    return command_path("npm")


def build_frontend(npm: str) -> None:
    if not (FRONTEND / "node_modules").is_dir():
        raise ProjectError("Frontend packages are missing. Run the setup command first.")
    run([npm, "run", "build"], cwd=FRONTEND)


def test() -> None:
    npm = require_setup()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "app")
    run([str(VENV_PYTHON), "-m", "pytest", "-q"], env=environment)
    build_frontend(npm)


def serve() -> None:
    npm = require_setup()
    build_frontend(npm)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "app")
    run(
        [str(VENV_PYTHON), "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"],
        env=environment,
    )


def generate_data() -> None:
    if not VENV_PYTHON.exists():
        raise ProjectError("Local Python environment is missing. Run the setup command first.")
    run([str(VENV_PYTHON), str(ROOT / "scripts" / "generate_scenarios.py")])


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up, check, test, or run BloodWatch on macOS and Windows.")
    parser.add_argument("action", choices=("doctor", "setup", "test", "run", "data"))
    arguments = parser.parse_args()
    try:
        if arguments.action == "doctor":
            return 0 if doctor() else 1
        if arguments.action == "setup":
            setup()
        elif arguments.action == "test":
            test()
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
