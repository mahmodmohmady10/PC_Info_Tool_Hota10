from core.data_models import CollectionResult
from core.windows_provider import first_cim
import socket


def collect_system() -> CollectionResult:
    result = CollectionResult(section="system")
    data, error = first_cim("ComputerSystem", ["Manufacturer", "Model", "Name", "TotalPhysicalMemory"])
    for key, label in [("Manufacturer", "manufacturer"), ("Model", "model"), ("Name", "computer_name")]:
        value = data.get(key) or (socket.gethostname() if key == "Name" else None)
        result.add(label, value, "Win32_ComputerSystem" if data else "socket", "available" if value else "unavailable")
    result.add("installed_memory", data.get("TotalPhysicalMemory"), "Win32_ComputerSystem",
               "available" if data.get("TotalPhysicalMemory") else "unavailable")
    if error:
        result.errors.append(error)
    return result.finalize()
