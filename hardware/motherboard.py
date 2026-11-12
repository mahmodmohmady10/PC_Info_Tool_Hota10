from core.data_models import CollectionResult
from core.windows_provider import first_cim


def collect_motherboard() -> CollectionResult:
    result = CollectionResult(section="motherboard")
    data, error = first_cim("BaseBoard", ["Manufacturer", "Product", "Version"])
    for output, key in [("manufacturer", "Manufacturer"), ("product", "Product"), ("version", "Version")]:
        value = data.get(key)
        result.add(output, value, "Win32_BaseBoard", "available" if value else "unavailable")
    bios, bios_error = first_cim("BIOS", ["SMBIOSBIOSVersion", "ReleaseDate", "Manufacturer"])
    result.add("bios_version", bios.get("SMBIOSBIOSVersion"), "Win32_BIOS",
               "available" if bios.get("SMBIOSBIOSVersion") else "unavailable")
    result.add("bios_manufacturer", bios.get("Manufacturer"), "Win32_BIOS",
               "available" if bios.get("Manufacturer") else "unavailable")
    if error:
        result.errors.append(error)
    if bios_error:
        result.errors.append(bios_error)
    return result.finalize()
