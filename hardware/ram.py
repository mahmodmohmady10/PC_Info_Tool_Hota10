from core.data_models import CollectionResult
from core.windows_provider import cim_query
from hardware.helpers import gb


def collect_ram() -> CollectionResult:
    result = CollectionResult(section="ram")
    rows, error = cim_query("PhysicalMemory", ["BankLabel", "DeviceLocator", "Capacity", "Manufacturer", "PartNumber", "Speed", "ConfiguredClockSpeed", "MemoryType", "SMBIOSMemoryType"])
    modules = []
    total = 0
    for row in rows:
        capacity = row.get("Capacity")
        try:
            total += int(capacity or 0)
        except (TypeError, ValueError):
            pass
        modules.append({
            "slot": row.get("DeviceLocator") or row.get("BankLabel"),
            "capacity": gb(capacity),
            "manufacturer": row.get("Manufacturer"),
            "part_number": (row.get("PartNumber") or "").strip() or None,
            "speed_mhz": row.get("ConfiguredClockSpeed") or row.get("Speed"),
            "memory_type_code": row.get("SMBIOSMemoryType") or row.get("MemoryType"),
        })
    result.add("modules", modules, "Win32_PhysicalMemory", "available" if modules else "unavailable")
    result.add("module_count", len(modules), "Win32_PhysicalMemory", "available" if modules else "unavailable")
    result.add("total_detected", gb(total) if total else None, "Win32_PhysicalMemory",
               "available" if total else "unavailable")
    if error:
        result.errors.append(error)
    return result.finalize()
