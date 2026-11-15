from __future__ import annotations

import html
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmarking import load_history
from diagnostics import run_diagnostics
from hardware import (
    collect_system, collect_cpu, collect_ram, collect_gpu,
    collect_motherboard, collect_storage, collect_battery, collect_os,
)


def _collect_hardware() -> dict[str, Any]:
    collected = {
        "system": collect_system(),
        "cpu": collect_cpu(),
        "ram": collect_ram(),
        "gpu": collect_gpu(),
        "motherboard": collect_motherboard(),
        "storage": collect_storage(),
        "battery": collect_battery(),
        "operating_system": collect_os(),
    }
    return {name: asdict(result) for name, result in collected.items()}


def build_report_data() -> dict[str, Any]:
    return {
        "application": "PC Info Tool 2.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "hardware": _collect_hardware(),
        "diagnostics": run_diagnostics(),
        "benchmark_history": load_history()[-200:],
        "limitations": [
            "نتائج التشخيص إرشادية وليست ضماناً لسلامة العتاد.",
            "حالة الأقراص تعتمد على ما يبلّغ عنه Windows ولا تمثل فحص SMART كاملاً.",
            "اختبارات الأداء قصيرة وتتأثر بالطاقة والبرامج المفتوحة ونوع المكونات.",
            "لا تتضمن هذه النسخة مراقبة درجات الحرارة.",
        ],
    }


def export_json_report(destination: str | Path) -> Path:
    path = Path(destination)
    payload = build_report_data()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _field_rows(section: dict[str, Any]) -> str:
    rows = []
    for name, item in section.get("fields", {}).items():
        value = item.get("value")
        value_text = "غير متاح" if value in (None, "", [], {}) else str(value)
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(name)), html.escape(value_text), html.escape(str(item.get("status", "")))
            )
        )
    if not rows:
        return '<tr><td colspan="3">لا توجد بيانات متاحة</td></tr>'
    return "".join(rows)


def export_html_report(destination: str | Path) -> Path:
    path = Path(destination)
    data = build_report_data()
    hardware_sections = []
    labels = {
        "system": "معلومات الجهاز", "cpu": "المعالج", "ram": "الذاكرة",
        "gpu": "بطاقة الرسوميات", "motherboard": "اللوحة الأم",
        "storage": "التخزين", "battery": "البطارية", "operating_system": "نظام التشغيل",
    }
    for key, section in data["hardware"].items():
        hardware_sections.append(
            f'<section><h2>{html.escape(labels.get(key, key))}</h2>'
            '<table><thead><tr><th>العنصر</th><th>القيمة</th><th>حالة القراءة</th></tr></thead>'
            f'<tbody>{_field_rows(section)}</tbody></table></section>'
        )

    diagnostics = data["diagnostics"]
    diagnostic_rows = []
    status_labels = {"good": "سليم", "warning": "تحذير", "problem": "مشكلة", "info": "معلومات"}
    for check in diagnostics.get("checks", []):
        diagnostic_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(check.get("title", ""))),
                html.escape(status_labels.get(check.get("status"), str(check.get("status", "")))),
                html.escape(str(check.get("value", ""))),
                html.escape(str(check.get("details", ""))),
            )
        )

    benchmark_rows = []
    for item in reversed(data["benchmark_history"][-50:]):
        benchmark_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(item.get("timestamp", ""))),
                html.escape(str(item.get("cpu_ops_per_second", "—"))),
                html.escape(str(item.get("memory_write_mbs", "—"))),
                html.escape(str(item.get("disk_write_mbs", "—"))),
                html.escape(str(item.get("disk_read_mbs", "—"))),
            )
        )
    if not benchmark_rows:
        benchmark_rows.append('<tr><td colspan="5">لا توجد اختبارات أداء محفوظة</td></tr>')

    limitations = "".join(f"<li>{html.escape(note)}</li>" for note in data["limitations"])
    generated = html.escape(data["generated_at"])
    counts = diagnostics.get("counts", {})
    document = f'''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>تقرير PC Info Tool 2.0</title><style>
:root{{color-scheme:light}}body{{font-family:Tahoma,Arial,sans-serif;background:#f3f5f9;color:#182230;margin:0;padding:28px;line-height:1.7}}
main{{max-width:1100px;margin:auto}}header,.panel,section{{background:#fff;border:1px solid #e3e8ef;border-radius:14px;padding:20px;margin-bottom:16px}}
header{{background:#14213d;color:#fff}}h1{{margin:0 0 6px;font-size:25px}}h2{{font-size:18px;margin:0 0 12px;color:#244a91}}p.meta{{color:#d4dced;margin:0}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px 10px;border-bottom:1px solid #e8edf3;text-align:right;vertical-align:top}}th{{background:#f0f4fa}}
.note{{background:#fff8e8;border-right:4px solid #d69e36;padding:12px;border-radius:8px}}footer{{color:#667085;text-align:center;font-size:12px;padding:12px}}
@media print{{body{{background:#fff;padding:0}}header,.panel,section{{break-inside:avoid;box-shadow:none}}}}
</style></head><body><main>
<header><h1>تقرير معلومات وتشخيص الجهاز</h1><p class="meta">PC Info Tool 2.0 · تاريخ الإنشاء: {generated}</p></header>
<div class="panel"><h2>ملخص التشخيص</h2><p>سليم: {counts.get('good',0)} · تحذير: {counts.get('warning',0)} · مشكلة: {counts.get('problem',0)} · معلومات: {counts.get('info',0)}</p><p>{html.escape(diagnostics.get('disclaimer',''))}</p></div>
<section><h2>نتائج التشخيص</h2><table><thead><tr><th>الفحص</th><th>النتيجة</th><th>القيمة</th><th>التفاصيل</th></tr></thead><tbody>{''.join(diagnostic_rows)}</tbody></table></section>
{''.join(hardware_sections)}
<section><h2>سجل الأداء (آخر 50 نتيجة)</h2><table><thead><tr><th>التاريخ</th><th>CPU عملية/ث</th><th>RAM كتابة MB/s</th><th>Disk كتابة MB/s</th><th>Disk قراءة MB/s</th></tr></thead><tbody>{''.join(benchmark_rows)}</tbody></table></section>
<section><h2>حدود التقرير</h2><ul>{limitations}</ul></section>
<footer>تم إنشاء هذا التقرير محلياً على الجهاز. راجع النتائج ولا تعتبرها بديلاً عن فحص فني متخصص.</footer>
</main></body></html>'''
    path.write_text(document, encoding="utf-8")
    return path
