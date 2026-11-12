from __future__ import annotations
import os
import time
import psutil

_last_net = None
_last_time = None


def reset_network_baseline() -> None:
    global _last_net, _last_time
    _last_net = psutil.net_io_counters()
    _last_time = time.monotonic()


def read_live_metrics() -> dict:
    """Read lightweight metrics; no persistent logging is performed."""
    global _last_net, _last_time
    now = time.monotonic()
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    drive = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        disk = psutil.disk_usage(drive)
    except Exception:
        disk = psutil.disk_usage(os.path.abspath(os.sep))
    net = psutil.net_io_counters()
    upload = download = 0.0
    if _last_net is not None and _last_time is not None:
        elapsed = max(now - _last_time, 0.001)
        upload = max(0, net.bytes_sent - _last_net.bytes_sent) / elapsed
        download = max(0, net.bytes_recv - _last_net.bytes_recv) / elapsed
    _last_net, _last_time = net, now
    return {
        "cpu_percent": float(cpu),
        "ram_percent": float(memory.percent),
        "ram_used_gb": memory.used / (1024 ** 3),
        "ram_total_gb": memory.total / (1024 ** 3),
        "disk_percent": float(disk.percent),
        "disk_used_gb": disk.used / (1024 ** 3),
        "disk_total_gb": disk.total / (1024 ** 3),
        "upload_bps": float(upload),
        "download_bps": float(download),
        "sampled_at": time.strftime("%H:%M:%S"),
    }
