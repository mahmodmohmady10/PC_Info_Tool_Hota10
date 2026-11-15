from __future__ import annotations

import csv
import json
import os
import platform
import tempfile
import time
from datetime import datetime
from pathlib import Path

import psutil

APP_DATA = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'PCInfoTool2'
HISTORY_FILE = APP_DATA / 'benchmark_history.json'


def run_benchmark() -> dict:
    """Run short, bounded CPU, memory and temporary-disk tests."""
    started = datetime.now().astimezone().isoformat(timespec='seconds')

    # CPU: fixed deterministic integer workload; no subprocesses or sustained stress.
    iterations = 1_200_000
    value = 0x12345678
    start = time.perf_counter()
    for i in range(iterations):
        value = ((value * 1664525) + 1013904223 + i) & 0xFFFFFFFF
    cpu_seconds = max(time.perf_counter() - start, 1e-9)
    cpu_ops = iterations / cpu_seconds

    # Memory: bounded 16 MiB buffer, write/read passes.
    size = 16 * 1024 * 1024
    block = bytearray(size)
    start = time.perf_counter()
    for offset in range(0, size, 4096):
        block[offset:offset + 4096] = b'P' * min(4096, size - offset)
    write_seconds = max(time.perf_counter() - start, 1e-9)
    start = time.perf_counter()
    checksum = sum(block[::64])
    read_seconds = max(time.perf_counter() - start, 1e-9)
    memory_write_mbs = (size / (1024 * 1024)) / write_seconds
    memory_read_mbs = ((size / 64) / (1024 * 1024)) / read_seconds
    del block

    # Disk: temporary 8 MiB file, flushed and deleted even if the test fails.
    disk_size = 8 * 1024 * 1024
    payload = b'PCInfoToolBenchmark' * (disk_size // len(b'PCInfoToolBenchmark'))
    fd, temp_name = tempfile.mkstemp(prefix='pcinfo_bench_', suffix='.tmp')
    os.close(fd)
    disk_write_mbs = disk_read_mbs = None
    try:
        start = time.perf_counter()
        with open(temp_name, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        disk_write_seconds = max(time.perf_counter() - start, 1e-9)
        start = time.perf_counter()
        with open(temp_name, 'rb') as handle:
            disk_checksum = len(handle.read())
        disk_read_seconds = max(time.perf_counter() - start, 1e-9)
        disk_write_mbs = (len(payload) / (1024 * 1024)) / disk_write_seconds
        disk_read_mbs = disk_checksum / (1024 * 1024) / disk_read_seconds
    finally:
        try:
            os.remove(temp_name)
        except OSError:
            pass

    memory = psutil.virtual_memory()
    drive = os.environ.get('SystemDrive', 'C:') + '\\'
    try:
        disk = psutil.disk_usage(drive)
    except Exception:
        disk = psutil.disk_usage(str(Path.home().anchor or '/'))
    result = {
        'timestamp': started,
        'platform': platform.platform(),
        'cpu_ops_per_second': round(cpu_ops, 1),
        'cpu_duration_seconds': round(cpu_seconds, 3),
        'memory_write_mbs': round(memory_write_mbs, 1),
        'memory_read_mbs': round(memory_read_mbs, 1),
        'disk_write_mbs': round(disk_write_mbs, 1),
        'disk_read_mbs': round(disk_read_mbs, 1),
        'ram_available_gb': round(memory.available / (1024 ** 3), 2),
        'disk_free_gb': round(disk.free / (1024 ** 3), 2),
        'checksum': int(value + checksum),
        'notes': 'نتائج تقريبية تتأثر بالبرامج المفتوحة والطاقة ونوع القرص؛ قارن الجهاز بنفسه وتحت ظروف متقاربة.'
    }
    return result


def load_history() -> list[dict]:
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_result(result: dict) -> None:
    APP_DATA.mkdir(parents=True, exist_ok=True)
    history = load_history()
    history.append(result)
    # Keep the most recent 200 benchmark runs.
    HISTORY_FILE.write_text(json.dumps(history[-200:], ensure_ascii=False, indent=2), encoding='utf-8')


def export_history_csv(destination: str) -> int:
    history = load_history()
    if not history:
        return 0
    fields = list(history[-1].keys())
    with open(destination, 'w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(history)
    return len(history)
