# PC Info Tool 2.0 — Phase 2 (GUI Foundation)

Independent Windows 10/11 desktop project. The original `pc_info_tool1.py` is untouched.

## What's included
- CustomTkinter desktop shell with Arabic navigation.
- Dark and light appearance modes.
- Dashboard cards connected to the Phase 1 collectors.
- Hardware details page for currently collected sections.
- Data collection runs on a worker thread so the UI does not freeze.
- Sections without an implemented engine are marked as under development; no fake readings are shown.
- CLI JSON mode remains available with `py main.py --cli`.

## Install
Open CMD or PowerShell in this folder and run:

```powershell
py -m pip install -r requirements.txt
```

## Run the graphical interface

```powershell
py main.py
```

## Run the JSON diagnostic output

```powershell
py main.py --cli
```

## Current scope / limitations
This is the first GUI foundation, not the finished application. Live monitoring, temperature sensors, diagnostics, benchmark, manual SQLite session history, and PDF/JSON report screens still need their own tested engines. The hardware page displays values returned by the current Windows CIM collectors, including unavailable states where Windows does not provide a value.

## Compatibility
- Windows 10/11
- Python 3.10+
