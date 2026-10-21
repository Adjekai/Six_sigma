# BloodWatch dependency setup for macOS and Windows

Do not install project packages globally and do not share a `.venv` folder. Each teammate creates a local environment from the pinned files in Git. The dashboard uses browser-native HTML, CSS, and JavaScript, so Node.js and npm are not required.

## Standard versions

- **Python:** 3.12–3.15; Python 3.14 and 3.15 are both supported team versions.
- **Git:** required for team collaboration.
- **Make:** optional. The cross-platform helper does not need it.

Check the machine before troubleshooting packages.

### macOS

```sh
python3 scripts/project.py doctor
```

### Windows PowerShell

```powershell
py scripts\project.py doctor
```

## Install Python

Use the official installer if the doctor reports Python missing:

- Python: <https://www.python.org/downloads/>

On Windows, enable the Python installer's **Add Python to PATH** option. After installing it, close and reopen the terminal before running the doctor again.

## One-time project setup

### macOS

```sh
python3 scripts/project.py setup
```

### Windows PowerShell

```powershell
py scripts\project.py setup
```

This creates an OS-specific `.venv`, installs the pinned Python packages, and regenerates the synthetic data. The frontend is served as static files and needs no separate installation or build.

## Run

### macOS

```sh
python3 scripts/project.py run
```

### Windows PowerShell

```powershell
py scripts\project.py run
```

Open <http://127.0.0.1:8000>. Stop the server with `Ctrl+C`.

## Test

### macOS

```sh
python3 scripts/project.py test
```

### Windows PowerShell

```powershell
py scripts\project.py test
```

## Common fixes

### `python`, `python3`, or `py` is not found

Install Python from the official installer, reopen the terminal, and run the doctor again. Windows commonly uses `py`; macOS commonly uses `python3`.

### The wrong Python version created `.venv`

Rename the existing `.venv` as a backup, select Python 3.14 or 3.15, and run setup again. Virtual environments are tied to their Python version and operating system, so teammates should not copy them between computers.

### Permission errors

Confirm the repository is in a folder the teammate owns. Do not run pip with `sudo` or Administrator privileges inside the project.

### Corporate proxy or certificate errors

These are network-policy issues rather than missing project dependencies. Record the full error and ask the organization's IT team for its approved pip proxy or certificate configuration. Do not disable TLS verification.

## Files that must remain local

The following are regenerated on each computer and are excluded from Git:

- `.venv/`

The pinned dependency records that must remain in Git are:

- `app/requirements.txt`
- `app/requirements-dev.txt`
