from core.data_models import CollectionResult
from core.windows_provider import cim_query
from hardware.helpers import gb


def collect_gpu() -> CollectionResult:
    result = CollectionResult(section="gpu")
    rows, error = cim_query("VideoController", ["Name", "AdapterRAM", "DriverVersion", "VideoProcessor", "CurrentHorizontalResolution", "CurrentVerticalResolution"])
    devices = []
    for row in rows:
        vram = gb(row.get("AdapterRAM"))
        devices.append({
            "name": row.get("Name"),
            "reported_adapter_memory": vram,
            "driver_version": row.get("DriverVersion"),
            "video_processor": row.get("VideoProcessor"),
            "resolution": (
                f'{row.get("CurrentHorizontalResolution")}x{row.get("CurrentVerticalResolution")}'
                if row.get("CurrentHorizontalResolution") and row.get("CurrentVerticalResolution") else None
            ),
            "memory_note": "Windows CIM AdapterRAM may be inaccurate; verify with vendor-specific API when available.",
        })
    result.add("devices", devices, "Win32_VideoController", "available" if devices else "unavailable")
    if error:
        result.errors.append(error)
    return result.finalize()
