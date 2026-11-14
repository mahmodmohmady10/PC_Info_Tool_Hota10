from __future__ import annotations

import os
import time
from datetime import datetime

import psutil

from core.windows_provider import cim_query


def _result(check_id: str, title: str, status: str, value: str, details: str, source: str) -> dict:
    return {
        "id": check_id,
        "title": title,
        "status": status,  # good, warning, problem, info
        "value": value,
        "details": details,
        "source": source,
    }


def run_diagnostics() -> dict:
    """Run read-only, lightweight checks. No stress tests or disk modifications."""
    checks: list[dict] = []

    # CPU: short sample, not a benchmark.
    try:
        cpu_percent = float(psutil.cpu_percent(interval=0.7))
        if cpu_percent >= 95:
            status, details = "warning", "الحمل مرتفع جداً أثناء أخذ العينة؛ أعد الفحص بعد إغلاق البرامج الثقيلة."
        elif cpu_percent >= 85:
            status, details = "warning", "استخدام المعالج مرتفع وقت الفحص، لكنه لا يثبت وجود عطل."
        else:
            status, details = "good", "استخدام المعالج ضمن الحدود المعتادة وقت أخذ العينة."
        checks.append(_result("cpu", "حمل المعالج", status, f"{cpu_percent:.1f}%", details, "psutil / CPU sample 0.7s"))
    except Exception as exc:
        checks.append(_result("cpu", "حمل المعالج", "info", "تعذر القياس", str(exc), "psutil"))

    # RAM pressure.
    try:
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024 ** 3)
        if mem.percent >= 95 or available_gb < 0.5:
            status, details = "problem", "الذاكرة المتاحة منخفضة جداً؛ أغلق التطبيقات غير الضرورية قبل تشغيل مهام إضافية."
        elif mem.percent >= 85 or available_gb < 1.0:
            status, details = "warning", "الذاكرة تحت ضغط ملحوظ. راجع التطبيقات الأعلى استهلاكاً."
        else:
            status, details = "good", "لا يظهر ضغط حاد على الذاكرة وقت الفحص."
        checks.append(_result("ram", "الذاكرة العشوائية", status,
                              f"{mem.percent:.1f}% مستخدم — {available_gb:.2f} GB متاح",
                              details, "psutil / virtual_memory"))
    except Exception as exc:
        checks.append(_result("ram", "الذاكرة العشوائية", "info", "تعذر القياس", str(exc), "psutil"))

    # System drive free space.
    drive = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        usage = psutil.disk_usage(drive)
        free_gb = usage.free / (1024 ** 3)
        if usage.percent >= 95 or free_gb < 5:
            status, details = "problem", "المساحة الحرة منخفضة جداً؛ احذف أو انقل الملفات بعد مراجعتها."
        elif usage.percent >= 90 or free_gb < 15:
            status, details = "warning", "المساحة الحرة محدودة وقد تؤثر في التحديثات والملفات المؤقتة."
        else:
            status, details = "good", "المساحة الحرة تبدو كافية للاستخدام المعتاد."
        checks.append(_result("disk_space", "مساحة قرص النظام", status,
                              f"{free_gb:.1f} GB متاح من {usage.total / (1024 ** 3):.1f} GB",
                              details, f"psutil / {drive}"))
    except Exception as exc:
        checks.append(_result("disk_space", "مساحة قرص النظام", "info", "تعذر القياس", str(exc), "psutil"))

    # Drive-reported status. This is not a full SMART/SSD health test.
    try:
        disks, error = cim_query("DiskDrive", ["Model", "Status", "DeviceID"])
        if disks:
            bad = [d for d in disks if str(d.get("Status") or "").strip().lower() in
                   {"pred fail", "error", "degraded", "failed", "unknown"}]
            statuses = [str(d.get("Status") or "غير محدد") for d in disks]
            if bad:
                status = "warning"
                details = "أبلغ Windows عن حالة تستحق التحقق لأحد الأقراص. هذه قراءة WMI أولية وليست تشخيص SMART كاملاً."
            elif all(str(d.get("Status") or "").strip().lower() == "ok" for d in disks):
                status = "good"
                details = "Windows يعرض حالة OK للأقراص المكتشفة؛ لا يعني ذلك ضمان سلامة القرص بالكامل."
            else:
                status = "info"
                details = "تم العثور على الأقراص، لكن Windows لم يقدم حالة حاسمة لكل قرص."
            summary = "، ".join(f"{d.get('Model') or 'قرص'}: {d.get('Status') or 'غير محدد'}" for d in disks)
            checks.append(_result("disk_status", "الحالة المعلنة للأقراص", status, summary, details, "Windows CIM / Win32_DiskDrive.Status"))
        else:
            checks.append(_result("disk_status", "الحالة المعلنة للأقراص", "info", "غير متاحة",
                                  error or "لم يرجع Windows بيانات للأقراص.", "Windows CIM"))
    except Exception as exc:
        checks.append(_result("disk_status", "الحالة المعلنة للأقراص", "info", "تعذر الفحص", str(exc), "Windows CIM"))

    # Network adapter state only; does not claim internet access.
    try:
        stats = psutil.net_if_stats()
        active = [name for name, item in stats.items() if item.isup and not name.lower().startswith(("loopback",))]
        if active:
            checks.append(_result("network", "محولات الشبكة", "good", f"{len(active)} محول نشط",
                                  "يوجد محول شبكة واحد على الأقل بحالة تشغيل. هذا لا يؤكد الوصول إلى الإنترنت.", "psutil / net_if_stats"))
        else:
            checks.append(_result("network", "محولات الشبكة", "warning", "لا يوجد محول نشط",
                                  "تحقق من Wi-Fi أو كابل الشبكة أو وضع الطيران.", "psutil / net_if_stats"))
    except Exception as exc:
        checks.append(_result("network", "محولات الشبكة", "info", "تعذر الفحص", str(exc), "psutil"))

    # Battery is optional on desktops.
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            checks.append(_result("battery", "البطارية", "info", "غير متاحة",
                                  "لم يتم العثور على بطارية أو أن Windows لا يتيح بياناتها؛ هذا طبيعي في بعض الأجهزة المكتبية.", "psutil / sensors_battery"))
        else:
            pct = float(battery.percent)
            if pct <= 10 and not battery.power_plugged:
                status, details = "warning", "مستوى البطارية منخفض جداً والجهاز غير موصول بالطاقة."
            elif pct <= 20 and not battery.power_plugged:
                status, details = "warning", "مستوى البطارية منخفض؛ يُفضّل توصيل الشاحن."
            else:
                status, details = "good", "مستوى الشحن لا يشير إلى خطر فوري. لا تتضمن هذه القراءة قياس صحة البطارية الكيميائية."
            power = "موصول بالشاحن" if battery.power_plugged else "يعمل على البطارية"
            checks.append(_result("battery", "البطارية", status, f"{pct:.0f}% — {power}", details, "psutil / sensors_battery"))
    except Exception as exc:
        checks.append(_result("battery", "البطارية", "info", "تعذر الفحص", str(exc), "psutil"))

    counts = {key: sum(1 for item in checks if item["status"] == key)
              for key in ("good", "warning", "problem", "info")}
    return {
        "checked_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "checks": checks,
        "counts": counts,
        "summary": "problem" if counts["problem"] else "warning" if counts["warning"] else "good",
        "disclaimer": "الفحص إرشادي وقرائي فقط. لا يجري اختبار ضغط، ولا يفحص SMART بشكل كامل، ولا يثبت سلامة العتاد نهائياً.",
    }
