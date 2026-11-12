# PC Info Tool 2.0 — Phase 3 (Live Monitor)

Independent Windows 10/11 desktop application. The original `pc_info_tool1.py` remains untouched.

## Phase 3 additions
- Live CPU usage.
- Live RAM usage.
- System-drive usage.
- Network upload/download throughput.
- Start/stop controls; refreshes every second while the Live Monitor page is open.
- No automatic persistent logging.
- No fabricated GPU or temperature values.

## Install
Open CMD or PowerShell in this folder and run:

```powershell
py -m pip install -r requirements.txt
```

## Run GUI

```powershell
py main.py
```

## JSON hardware report

```powershell
py main.py --cli
```

## Current limitations
GPU utilization, CPU/GPU temperatures, diagnostics, benchmarks, SQLite session history, and PDF reports are not implemented yet.
