from core.data_models import CollectionResult
from core.windows_provider import cim_query
import psutil


def collect_storage() -> CollectionResult:
    result = CollectionResult(section="storage")
    rows, error = cim_query("DiskDrive", ["Model", "MediaType", "InterfaceType", "Size", "SerialNumber", "Status"])
    disks = []
    for row in rows:
        try:
            size = f'{int(row["Size"]) / (1024 ** 3):.2f} GB' if row.get("Size") else None
        except (TypeError, ValueError):
            size = None
        disks.append({
            "model": row.get("Model"), "media_type": row.get("MediaType"),
            "interface": row.get("InterfaceType"), "capacity": size,
            "status": row.get("Status"),
            # Serial number intentionally omitted from reports by default.
        })
    partitions = []
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device, "mountpoint": part.mountpoint,
                    "total_bytes": usage.total, "used_bytes": usage.used,
                    "free_bytes": usage.free, "percent_used": usage.percent,
                })
            except (PermissionError, OSError):
                continue
    except Exception as exc:
        result.errors.append(f"Partition usage: {exc}")
    result.add("physical_disks", disks, "Win32_DiskDrive", "available" if disks else "unavailable")
    result.add("partitions", partitions, "psutil", "available" if partitions else "unavailable")
    if error:
        result.errors.append(error)
    return result.finalize()
