from core.data_models import CollectionResult
from core.windows_provider import first_cim


def collect_cpu() -> CollectionResult:
    result = CollectionResult(section="cpu")
    data, error = first_cim("Processor", ["Name", "Manufacturer", "NumberOfCores", "NumberOfLogicalProcessors", "MaxClockSpeed", "Architecture"])
    fields = {
        "name": "Name", "manufacturer": "Manufacturer", "physical_cores": "NumberOfCores",
        "logical_processors": "NumberOfLogicalProcessors", "max_clock_mhz": "MaxClockSpeed",
        "architecture_code": "Architecture",
    }
    for output, source_key in fields.items():
        value = data.get(source_key)
        result.add(output, value, "Win32_Processor", "available" if value is not None else "unavailable")
    if error:
        result.errors.append(error)
    return result.finalize()
