from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


def run_powershell(command: str, timeout: int = 15) -> tuple[str, str | None]:
    """Run a read-only PowerShell query. Returns (stdout, error)."""
    if sys.platform != "win32":
        return "", "Windows-only provider"

    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            return completed.stdout.strip(), completed.stderr.strip() or f"PowerShell exit code {completed.returncode}"
        return completed.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return "", f"PowerShell query timed out after {timeout}s"
    except FileNotFoundError:
        return "", "PowerShell executable not found"
    except Exception as exc:
        return "", str(exc)


def cim_query(class_name: str, properties: list[str], timeout: int = 15) -> tuple[list[dict[str, Any]], str | None]:
    """Query Win32_* CIM class and normalize single-object/array JSON output."""
    safe_class = "".join(ch for ch in class_name if ch.isalnum() or ch == "_")
    safe_props = [p for p in properties if p.replace("_", "").isalnum()]
    if not safe_class or not safe_props:
        return [], "Invalid CIM query"

    prop_list = ",".join(safe_props)
    command = (
        f"$ErrorActionPreference='Stop'; "
        f"Get-CimInstance -ClassName 'Win32_{safe_class}' | "
        f"Select-Object -Property {prop_list} | ConvertTo-Json -Compress -Depth 3"
    )
    raw, error = run_powershell(command, timeout=timeout)
    if error:
        return [], error
    if not raw:
        return [], None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return [data], None
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)], None
        return [], "Unexpected JSON structure"
    except json.JSONDecodeError as exc:
        return [], f"Could not parse CIM JSON: {exc}"


def first_cim(class_name: str, properties: list[str]) -> tuple[dict[str, Any], str | None]:
    rows, error = cim_query(class_name, properties)
    return (rows[0] if rows else {}), error
