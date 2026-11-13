# PC Info Tool 2.0 — Phase 3 (Live Monitor)

Independent Windows 10/11 desktop application. The original `pc_info_tool1.py` remains untouched.

## Phase 3 additions
- Live CPU usage.
- Live RAM usage.
- System-drive usage.
- Network upload/download throughput.
- Start/stop controls; refreshes every second while the Live Monitor page is open.
- No automatic persistent logging.
- No fabricated GPU or temperature values.

## Install
Open CMD or PowerShell in this folder and run:

```powershell
py -m pip install -r requirements.txt
```

## Run GUI

```powershell
py main.py
```

## JSON hardware report

```powershell
py main.py --cli
```

## Current limitations
GPU utilization, CPU/GPU temperatures, diagnostics, benchmarks, SQLite session history, and PDF reports are not implemented yet.


---

## Phase 4 — Temperature Monitoring

### Added
- Arabic temperature sensors page connected to the existing sidebar item.
- LibreHardwareMonitor WMI temperature sensor reader.
- Windows ACPI thermal-zone reader through `root\wmi`.
- Independent status and source information for each provider.
- Background collection thread to keep the GUI responsive.
- Manual refresh control.
- Explicit unavailable/unsupported states; no fabricated temperature values.

### Important limitations
- LibreHardwareMonitor must be installed/launched and expose its WMI provider for those readings to appear.
- Windows ACPI thermal zones are not guaranteed to be CPU package temperature.
- Actual sensor availability and readings must be verified on the target Windows device.

### Validation
- Python syntax compilation is performed before packaging.
- Runtime hardware sensor validation is pending user testing.

## Cumulative project status
- Phase 1: hardware collectors and CLI JSON output — initial test completed.
- Phase 2: Arabic GUI, dashboard, hardware page, dark/light modes — user confirmed GUI opens.
- Phase 3: live CPU/RAM/system-drive/network monitoring — user supplied screenshot showing readings.
- Phase 4: temperature integration — implemented in this package; device validation pending.

## Next phase
- Phase 5: diagnostics with evidence-based checks and clear warnings.


## تحديث المرحلة الرابعة بعد اختبار الجهاز
- أضيف مصدر LibreHardwareMonitor REST على `http://localhost:8085/data.json` كمصدر أساسي لقراءات الحرارة.
- يجب تشغيل LibreHardwareMonitor وتفعيل `Options > Remote Web Server > Run`.
- يتم اعتماد الحقل `Type` بحيث لا تُخلط مستشعرات الجهد أو الطاقة أو التردد مع الحرارة؛ لا تُقبل إلا المستشعرات من النوع `Temperature`.
- أضيف تحديث تلقائي كل 5 ثوانٍ عند فتح صفحة الحرارة، مع تجنب تداخل عمليات التحديث.
- تبقى قنوات WMI وWindows ACPI ظاهرة للتشخيص، لكنها ليست المصدر الأساسي.
- اختبار المستخدم أكد ظهور حرارة CPU Package وCore Max وCore Average والأنوية والقرص عبر REST. القيم المرسلة كانت لقطة وقت الاختبار وليست اختبار ضغط.
