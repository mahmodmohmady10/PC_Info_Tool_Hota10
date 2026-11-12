from core.data_models import CollectionResult
from core.windows_provider import first_cim
import platform


def collect_os() -> CollectionResult:
    result = CollectionResult(section="operating_system")
    data, error = first_cim("OperatingSystem", ["Caption", "Version", "BuildNumber", "OSArchitecture", "LastBootUpTime"])
    fallback = {
        "name": platform.system(), "version": platform.version(),
        "architecture": platform.machine(), "python_version": platform.python_version(),
    }
    mapping = {
        "name": ("Caption", fallback["name"]),
        "version": ("Version", fallback["version"]),
        "build": ("BuildNumber", None),
        "architecture": ("OSArchitecture", fallback["architecture"]),
        "last_boot": ("LastBootUpTime", None),
    }
    for output, (key, default) in mapping.items():
        value = data.get(key) or default
        result.add(output, value, "Win32_OperatingSystem" if data.get(key) else "platform",
                   "available" if value else "unavailable")
    result.add("python_version", fallback["python_version"], "platform")
    if error:
        result.errors.append(error)
    return result.finalize()
