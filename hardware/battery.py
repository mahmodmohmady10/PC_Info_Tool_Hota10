from core.data_models import CollectionResult
try:
    import psutil
except ImportError:
    psutil = None


def collect_battery() -> CollectionResult:
    result = CollectionResult(section="battery")
    if psutil is None:
        result.add_unavailable("status", "psutil", "unsupported", "Install psutil to read battery data.")
        return result.finalize()
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            result.add_unavailable("status", "psutil", "unsupported", "No battery detected or sensor unavailable.")
        else:
            result.add("percent", battery.percent, "psutil")
            result.add("power_plugged", battery.power_plugged, "psutil")
            result.add("seconds_left", battery.secsleft if battery.secsleft >= 0 else None, "psutil")
    except Exception as exc:
        result.errors.append(str(exc))
        result.add_unavailable("status", "psutil", "error")
    return result.finalize()
