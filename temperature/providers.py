from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime


def _run_powershell(script: str, timeout: int = 12):
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "RemoteSigned", "-Command", script
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception as exc:
        return False, None, str(exc)

    if result.returncode != 0:
        error = (result.stderr or result.stdout or "PowerShell query failed").strip()
        return False, None, error[:500]

    output = result.stdout.strip()
    if not output:
        return True, [], ""
    try:
        return True, json.loads(output), ""
    except json.JSONDecodeError:
        return False, None, "تعذر تحليل استجابة Windows."


def read_windows_acpi_zones():
    """ACPI zones are general thermal zones, not guaranteed CPU package readings."""
    script = r"""
    $ErrorActionPreference = 'Stop'
    try {
      $items = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature |
        Select-Object InstanceName, CurrentTemperature
      $items | ConvertTo-Json -Compress -Depth 4
    } catch { Write-Error $_; exit 1 }
    """
    ok, data, error = _run_powershell(script)
    if not ok:
        return {
            "source": "Windows ACPI / root\\wmi",
            "status": "unavailable",
            "note": error,
            "sensors": []
        }

    if isinstance(data, dict):
        data = [data]

    sensors = []
    for item in data or []:
        try:
            celsius = float(item["CurrentTemperature"]) / 10.0 - 273.15
        except (KeyError, TypeError, ValueError):
            continue
        sensors.append({
            "name": str(item.get("InstanceName") or "ACPI thermal zone"),
            "temperature_c": round(celsius, 1)
        })

    return {
        "source": "Windows ACPI / root\\wmi",
        "status": "available" if sensors else "unsupported",
        "note": (
            "هذه قراءات مناطق ACPI العامة، ولا تمثل بالضرورة حرارة المعالج."
            if sensors else "لم يُرجع Windows أي مناطق حرارية متاحة."
        ),
        "sensors": sensors
    }


def read_libre_hardware_monitor():
    """Reads LHM WMI sensors when LibreHardwareMonitor exposes its WMI provider."""
    script = r"""
    $ErrorActionPreference = 'Stop'
    try {
      $items = Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor |
        Where-Object { $_.SensorType -eq 'Temperature' } |
        Select-Object Name, Parent, Identifier, Value
      $items | ConvertTo-Json -Compress -Depth 4
    } catch { Write-Error $_; exit 1 }
    """
    ok, data, error = _run_powershell(script)
    if not ok:
        return {
            "source": "LibreHardwareMonitor WMI",
            "status": "unavailable",
            "note": "تعذر الوصول إلى مزود LibreHardwareMonitor: " + error,
            "sensors": []
        }

    if isinstance(data, dict):
        data = [data]

    sensors = []
    for item in data or []:
        try:
            value = float(item.get("Value"))
        except (TypeError, ValueError):
            continue
        sensors.append({
            "name": str(item.get("Name") or "Temperature"),
            "parent": str(item.get("Parent") or ""),
            "identifier": str(item.get("Identifier") or ""),
            "temperature_c": round(value, 1)
        })

    return {
        "source": "LibreHardwareMonitor WMI",
        "status": "available" if sensors else "unsupported",
        "note": (
            "قراءات مستشعرات الحرارة التي أبلغ عنها LibreHardwareMonitor."
            if sensors else "المزود متاح، لكنه لم يُرجع مستشعرات حرارة."
        ),
        "sensors": sensors
    }



def read_libre_hardware_monitor_rest(url: str = "http://localhost:8085/data.json"):
    """Read temperature sensors from LibreHardwareMonitor's local REST JSON tree."""
    from urllib.request import build_opener, ProxyHandler, Request
    from urllib.error import URLError, HTTPError

    try:
        # localhost must bypass system HTTP proxies; this is a local-only endpoint.
        opener = build_opener(ProxyHandler({}))
        request = Request(url, headers={"Accept": "application/json"})
        with opener.open(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "source": "LibreHardwareMonitor REST",
            "status": "unavailable",
            "note": (
                "تعذر الاتصال بخادم LibreHardwareMonitor المحلي. "
                "تأكد من تشغيل البرنامج وتفعيل Remote Web Server."
            ),
            "sensors": [],
        }

    sensors = []

    def walk(nodes, path=""):
        if isinstance(nodes, dict):
            nodes = [nodes]
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("Text") or "Sensor")
            current_path = f"{path}/{name}"
            sensor_type = str(node.get("Type") or "").strip().lower()
            # Type is essential: names such as CPU Core #1 also occur for voltage and clocks.
            if sensor_type == "temperature":
                raw_value = str(node.get("Value") or "").strip()
                match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?\s*C", raw_value, re.I)
                if match:
                    value = float(match.group(1))
                    sensor_id = str(node.get("SensorId") or "")
                    sensors.append({
                        "name": name,
                        "path": current_path,
                        "identifier": sensor_id,
                        "temperature_c": round(value, 1),
                        "category": (
                            "cpu" if "/intelcpu/" in sensor_id.lower()
                            else "gpu" if "/gpu/" in sensor_id.lower()
                            else "storage" if "/hdd/" in sensor_id.lower() or "/nvme/" in sensor_id.lower()
                            else "other"
                        ),
                    })
            walk(node.get("Children") or [], current_path)

    walk(payload)
    return {
        "source": "LibreHardwareMonitor REST",
        "status": "available" if sensors else "unsupported",
        "note": (
            "قراءات الحرارة مأخوذة من مستشعرات نوع Temperature فقط."
            if sensors else "تم الاتصال بالخادم، لكن لم تُعثر على مستشعرات حرارة بقيم قابلة للقراءة."
        ),
        "sensors": sensors,
    }


def collect_temperature_report():
    return {
        "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "providers": [
            read_libre_hardware_monitor_rest(),
            read_libre_hardware_monitor(),
            read_windows_acpi_zones()
        ],
        "important_note": (
            "المصدر الأساسي هو REST المحلي لـ LibreHardwareMonitor. "
            "يجب تشغيل البرنامج وتفعيل Remote Web Server. "
            "يتم تجاهل المستشعرات التي لا يكون نوعها Temperature."
        )
    }
