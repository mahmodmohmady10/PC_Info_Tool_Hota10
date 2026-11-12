from __future__ import annotations

import argparse
import json
import platform
import threading
import queue
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from monitoring.live_metrics import read_live_metrics, reset_network_baseline

from hardware import (
    collect_system, collect_cpu, collect_ram, collect_gpu,
    collect_motherboard, collect_storage, collect_battery, collect_os,
)

APP_NAME = "PC INFO TOOL"
APP_VERSION = "2.0  |  PHASE 2"


def collect_all():
    return {
        "system": collect_system(),
        "cpu": collect_cpu(),
        "ram": collect_ram(),
        "gpu": collect_gpu(),
        "motherboard": collect_motherboard(),
        "storage": collect_storage(),
        "battery": collect_battery(),
        "operating_system": collect_os(),
    }


def plain_value(section, key, default="غير متاح"):
    item = section.fields.get(key)
    if not item or item.value in (None, "", [], {}):
        return default
    return str(item.value)


def run_cli():
    report = collect_all()
    payload = {
        "application": "PC Info Tool 2.0",
        "platform": platform.platform(),
        "sections": {name: asdict(result) for name, result in report.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


class InfoCard(ctk.CTkFrame):
    def __init__(self, master, title, value="—", hint="", **kwargs):
        super().__init__(master, corner_radius=14, border_width=1, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#667085", "#A7B0C0")).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 5))
        self.value_label = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(size=19, weight="bold"),
                                        anchor="w", justify="left", wraplength=250)
        self.value_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.hint_label = ctk.CTkLabel(self, text=hint, font=ctk.CTkFont(size=11),
                                       text_color=("#667085", "#929BAA"), anchor="w")
        self.hint_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))

    def set_value(self, value, hint=None):
        self.value_label.configure(text=value)
        if hint is not None:
            self.hint_label.configure(text=hint)


class PCInfoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(fg_color=("#F4F6FA", "#0B1020"))
        self.data = {}
        self.worker_queue = queue.Queue()
        self.active_page = "Dashboard"
        self.monitor_running = False
        self.monitor_after_id = None
        self.metric_labels = {}
        self.metric_bars = {}
        self.nav_buttons = {}
        self._build_shell()
        self.show_page("Dashboard")
        self.refresh_data()
        self.after(150, self._poll_queue)

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=225, corner_radius=0, fg_color=("#FFFFFF", "#11182A"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(25, 30))
        ctk.CTkLabel(brand, text="◈", text_color="#6C8CFF", font=ctk.CTkFont(size=30, weight="bold")).pack(side="left")
        name_box = ctk.CTkFrame(brand, fg_color="transparent")
        name_box.pack(side="left", padx=9)
        ctk.CTkLabel(name_box, text="PC INFO TOOL", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(name_box, text="SYSTEM INSIGHTS", font=ctk.CTkFont(size=9), text_color=("#7B8495", "#8792A6")).pack(anchor="w")

        nav_items = [
            ("Dashboard", "▦", "لوحة التحكم"),
            ("Hardware", "▣", "مكونات الجهاز"),
            ("Live Monitor", "◷", "المراقبة المباشرة"),
            ("Temperature", "♨", "درجات الحرارة"),
            ("Diagnostics", "✓", "التشخيص"),
            ("Benchmark", "⌁", "اختبار الأداء"),
            ("History", "◴", "السجل"),
            ("Reports", "▤", "التقارير"),
        ]
        for key, glyph, label in nav_items:
            btn = ctk.CTkButton(self.sidebar, text=f"{glyph}    {label}", anchor="w", height=42,
                                corner_radius=9, fg_color="transparent", text_color=("#344054", "#D6DCEC"),
                                hover_color=("#EEF2FF", "#202B45"),
                                command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = btn

        ctk.CTkFrame(self.sidebar, height=1, fg_color=("#E6EAF0", "#273149")).pack(fill="x", padx=16, pady=(22, 14))
        ctk.CTkButton(self.sidebar, text="⚙    الإعدادات", anchor="w", height=40,
                      fg_color="transparent", text_color=("#344054", "#D6DCEC"),
                      hover_color=("#EEF2FF", "#202B45"), command=lambda: self.show_page("Settings")).pack(fill="x", padx=12)
        ctk.CTkLabel(self.sidebar, text="PC Info Tool 2.0\nنسخة تطويرية — Phase 2", justify="left",
                     text_color=("#98A2B3", "#667085"), font=ctk.CTkFont(size=10)).pack(side="bottom", anchor="w", padx=18, pady=18)

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=26, pady=22)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        top.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(top, text="لوحة التحكم", font=ctk.CTkFont(size=25, weight="bold"))
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_subtitle = ctk.CTkLabel(top, text="نظرة عامة على حالة ومكونات جهازك", text_color=("#667085", "#9AA5B8"), font=ctk.CTkFont(size=12))
        self.page_subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkButton(top, text="↻  تحديث البيانات", width=135, height=36, command=self.refresh_data).grid(row=0, column=1, rowspan=2, padx=(10, 8))
        self.mode_switch = ctk.CTkSegmentedButton(top, values=["Dark", "Light"], width=125, command=self.change_mode)
        self.mode_switch.set("Dark")
        self.mode_switch.grid(row=0, column=2, rowspan=2)

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def change_mode(self, value):
        ctk.set_appearance_mode(value.lower())

    def show_page(self, page):
        if self.active_page == "Live Monitor" and page != "Live Monitor":
            self.stop_monitoring()
        self.active_page = page
        for key, button in self.nav_buttons.items():
            button.configure(fg_color=("#E8EEFF", "#26365B") if key == page else "transparent",
                             text_color=("#3156C8", "#AFC2FF") if key == page else ("#344054", "#D6DCEC"))
        titles = {
            "Dashboard": ("لوحة التحكم", "نظرة عامة على حالة ومكونات جهازك"),
            "Hardware": ("مكونات الجهاز", "تفاصيل المعالج والذاكرة والرسوميات والتخزين"),
            "Live Monitor": ("المراقبة المباشرة", "متابعة استهلاك المعالج والذاكرة والتخزين والشبكة"),
            "Temperature": ("درجات الحرارة", "مصادر قياس الحرارة ستضاف في المرحلة التالية"),
            "Diagnostics": ("تشخيص الجهاز", "فحوصات منظمة مع توضيح الأدلة والنتائج"),
            "Benchmark": ("اختبار الأداء", "اختبارات قصيرة وآمنة لأداء المكونات"),
            "History": ("السجل", "حفظ الجلسات ومقارنة النتائج يدوياً"),
            "Reports": ("التقارير", "تصدير تقرير الجهاز بصيغ متعددة"),
            "Settings": ("الإعدادات", "تفضيلات التطبيق ومصادر جمع البيانات"),
        }
        title, subtitle = titles.get(page, (page, ""))
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        for child in self.content.winfo_children():
            child.destroy()
        if page == "Dashboard":
            self._build_dashboard()
        elif page == "Hardware":
            self._build_hardware()
        elif page == "Live Monitor":
            self._build_live_monitor()
        elif page == "Settings":
            self._build_settings()
        else:
            self._build_coming_soon(page)

    def _build_dashboard(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure((0, 1, 2), weight=1)

        hero = ctk.CTkFrame(wrap, corner_radius=16, fg_color=("#FFFFFF", "#151F35"), border_width=1)
        hero.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 16))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="مرحباً بك في PC Info Tool", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(18, 4))
        ctk.CTkLabel(hero, text="اجمع معلومات جهازك، راقب حالته، وافهم أداء مكوناته من مكان واحد.",
                     text_color=("#667085", "#A7B0C0"), font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="w", padx=22, pady=(0, 18))
        self.status_label = ctk.CTkLabel(hero, text="●  جاري تجهيز البيانات...", text_color="#D69E36", font=ctk.CTkFont(size=11, weight="bold"))
        self.status_label.grid(row=0, column=1, rowspan=2, padx=22)

        self.cards = {}
        card_specs = [
            ("cpu", "المعالج CPU", "جاري القراءة...", "اسم ومواصفات المعالج"),
            ("ram", "الذاكرة RAM", "جاري القراءة...", "إجمالي الذاكرة المكتشفة"),
            ("gpu", "كرت الشاشة GPU", "جاري القراءة...", "بطاقة الرسوميات"),
            ("storage", "التخزين", "جاري القراءة...", "الأقراص ووحدات التخزين"),
            ("os", "نظام التشغيل", "جاري القراءة...", "إصدار Windows"),
            ("device", "الشركة والطراز", "جاري القراءة...", "معلومات الجهاز"),
        ]
        for index, (key, title, value, hint) in enumerate(card_specs):
            card = InfoCard(wrap, title, value, hint, fg_color=("#FFFFFF", "#151F35"), border_color=("#E4E7EC", "#263149"))
            card.grid(row=1 + index // 3, column=index % 3, sticky="nsew", padx=5, pady=5)
            self.cards[key] = card

        note = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#EEF3FF", "#172542"))
        note.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=(16, 5))
        ctk.CTkLabel(note, text="ملاحظة الإصدار", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#3156C8", "#AFC2FF")).pack(anchor="w", padx=16, pady=(13, 4))
        ctk.CTkLabel(note, text="هذه نسخة الواجهة الأولى. أقسام المراقبة والحرارة والتشخيص والاختبارات والسجل ستُفعّل تدريجياً بعد اختبار كل وحدة.",
                     justify="left", wraplength=800, text_color=("#475467", "#B8C4D9")).pack(anchor="w", padx=16, pady=(0, 13))
        if self.data:
            self._update_dashboard_cards()

    def _update_dashboard_cards(self):
        if not hasattr(self, "cards"):
            return
        cpu = self.data.get("cpu")
        ram = self.data.get("ram")
        gpu = self.data.get("gpu")
        storage = self.data.get("storage")
        os_data = self.data.get("operating_system")
        system = self.data.get("system")
        if cpu:
            self.cards["cpu"].set_value(plain_value(cpu, "name"), f"{plain_value(cpu, 'physical_cores', '؟')} أنوية / {plain_value(cpu, 'logical_processors', '؟')} مسارات")
        if ram:
            self.cards["ram"].set_value(plain_value(ram, "total_detected"), f"عدد الوحدات: {plain_value(ram, 'module_count', '؟')}")
        if gpu:
            devices = gpu.fields.get("devices").value if gpu.fields.get("devices") else []
            names = [d.get("name") for d in devices if d.get("name")]
            self.cards["gpu"].set_value("\n".join(names) if names else "غير متاح", f"عدد البطاقات: {len(names)}")
        if storage:
            disks = storage.fields.get("physical_disks") or storage.fields.get("partitions")
            values = disks.value if disks else None
            self.cards["storage"].set_value(f"{len(values)} وحدات" if isinstance(values, list) else "تم الفحص", "وحدات التخزين المكتشفة")
        if os_data:
            self.cards["os"].set_value(plain_value(os_data, "name"), plain_value(os_data, "version"))
        if system:
            self.cards["device"].set_value(plain_value(system, "manufacturer"), plain_value(system, "model"))
        if hasattr(self, "status_label"):
            self.status_label.configure(text="●  اكتمل جمع البيانات", text_color="#21A179")

    def _build_hardware(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        if not self.data:
            ctk.CTkLabel(frame, text="لا توجد بيانات بعد. اضغط تحديث البيانات.").grid(row=0, column=0, pady=30)
            return
        sections = [
            ("معلومات الجهاز", "system", ["manufacturer", "model", "computer_name"]),
            ("المعالج", "cpu", ["name", "manufacturer", "physical_cores", "logical_processors", "max_clock_mhz"]),
            ("الذاكرة", "ram", ["total_detected", "module_count", "modules"]),
            ("الرسوميات", "gpu", ["devices"]),
            ("اللوحة الأم", "motherboard", ["manufacturer", "product", "version", "bios_version", "bios_manufacturer"]),
            ("نظام التشغيل", "operating_system", ["name", "version", "build", "architecture", "last_boot"]),
            ("البطارية", "battery", ["percent", "power_plugged", "seconds_left"]),
            ("التخزين", "storage", ["physical_disks", "partitions"]),
        ]
        for row, (title, key, fields) in enumerate(sections):
            result = self.data.get(key)
            panel = ctk.CTkFrame(frame, corner_radius=12, fg_color=("#FFFFFF", "#151F35"), border_width=1,
                                 border_color=("#E4E7EC", "#263149"))
            panel.grid(row=row, column=0, sticky="ew", padx=4, pady=5)
            panel.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(panel, text=title, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 7))
            for i, field in enumerate(fields, start=1):
                value = plain_value(result, field) if result else "غير متاح"
                if field in ("modules", "devices") and result and result.fields.get(field):
                    value = json.dumps(result.fields[field].value, ensure_ascii=False, indent=2, default=str)
                ctk.CTkLabel(panel, text=field.replace("_", " "), text_color=("#667085", "#A7B0C0"), anchor="w").grid(row=i, column=0, sticky="nw", padx=15, pady=4)
                ctk.CTkLabel(panel, text=value, anchor="w", justify="left", wraplength=690).grid(row=i, column=1, sticky="ew", padx=15, pady=4)
            ctk.CTkLabel(panel, text=f"حالة الجمع: {result.status if result else 'لم يتم الجمع'}",
                         text_color="#21A179" if result and result.status == "available" else ("#B7791F", "#D6A34A"),
                         font=ctk.CTkFont(size=10)).grid(row=len(fields)+1, column=0, columnspan=2, sticky="w", padx=15, pady=(5, 11))

    def _build_live_monitor(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure((0, 1), weight=1)

        head = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#FFFFFF", "#151F35"),
                            border_width=1, border_color=("#E4E7EC", "#263149"))
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 12))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="مراقبة موارد الجهاز",
                     font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(15, 3))
        self.monitor_status = ctk.CTkLabel(head, text="متوقفة",
                                           text_color=("#667085", "#A7B0C0"))
        self.monitor_status.grid(row=0, column=1, padx=16)

        controls = ctk.CTkFrame(head, fg_color="transparent")
        controls.grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(7, 14))
        self.monitor_start_btn = ctk.CTkButton(controls, text="▶ بدء المراقبة", width=130,
                                               command=self.start_monitoring)
        self.monitor_start_btn.pack(side="left", padx=4)
        self.monitor_stop_btn = ctk.CTkButton(
            controls, text="■ إيقاف", width=100, fg_color=("#E9EDF5", "#29344A"),
            text_color=("#344054", "#E3E8F2"), hover_color=("#DDE3ED", "#36435D"),
            command=self.stop_monitoring, state="disabled")
        self.monitor_stop_btn.pack(side="left", padx=4)
        self.monitor_timestamp = ctk.CTkLabel(controls, text="لم تبدأ القراءة بعد",
                                               text_color=("#667085", "#A7B0C0"))
        self.monitor_timestamp.pack(side="left", padx=12)

        self.metric_labels = {}
        self.metric_bars = {}
        for idx, (key, title) in enumerate([
            ("cpu", "استخدام المعالج"), ("ram", "استخدام الذاكرة"),
            ("disk", "استخدام قرص النظام")]):
            card = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#FFFFFF", "#151F35"),
                                border_width=1, border_color=("#E4E7EC", "#263149"))
            card.grid(row=1 + idx // 2, column=idx % 2, sticky="ew", padx=4, pady=5)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=("#667085", "#A7B0C0")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(14, 5))
            value = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=25, weight="bold"))
            value.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
            bar = ctk.CTkProgressBar(card, height=10)
            bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 15))
            bar.set(0)
            self.metric_labels[key] = value
            self.metric_bars[key] = bar

        net_card = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#FFFFFF", "#151F35"),
                                border_width=1, border_color=("#E4E7EC", "#263149"))
        net_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=5)
        net_card.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(net_card, text="حركة الشبكة", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))
        self.metric_labels["download"] = ctk.CTkLabel(
            net_card, text="التنزيل: —", font=ctk.CTkFont(size=15, weight="bold"))
        self.metric_labels["download"].grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))
        self.metric_labels["upload"] = ctk.CTkLabel(
            net_card, text="الرفع: —", font=ctk.CTkFont(size=15, weight="bold"))
        self.metric_labels["upload"].grid(row=1, column=1, sticky="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(
            wrap,
            text=("هذه المرحلة تقيس CPU وRAM والقرص والشبكة. لا تعرض حرارة أو استخدام GPU حالياً؛ "
                  "لن نضع قيماً تقديرية مكان الحساسات الحقيقية."),
            wraplength=850, justify="left", text_color=("#667085", "#A7B0C0")
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=12)

    @staticmethod
    def _format_rate(value):
        amount = float(value)
        for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
            if amount < 1024 or unit == "GB/s":
                return f"{amount:.1f} {unit}"
            amount /= 1024

    def start_monitoring(self):
        if self.monitor_running:
            return
        self.monitor_running = True
        reset_network_baseline()
        self.monitor_status.configure(text="● تعمل الآن", text_color="#21A179")
        self.monitor_start_btn.configure(state="disabled")
        self.monitor_stop_btn.configure(state="normal")
        self._update_live_metrics()

    def stop_monitoring(self):
        self.monitor_running = False
        if self.monitor_after_id is not None:
            try:
                self.after_cancel(self.monitor_after_id)
            except Exception:
                pass
            self.monitor_after_id = None
        if hasattr(self, "monitor_status"):
            self.monitor_status.configure(text="متوقفة", text_color=("#667085", "#A7B0C0"))
            self.monitor_start_btn.configure(state="normal")
            self.monitor_stop_btn.configure(state="disabled")

    def _update_live_metrics(self):
        if not self.monitor_running or self.active_page != "Live Monitor":
            return
        try:
            metrics = read_live_metrics()
            for key, field in (("cpu", "cpu_percent"), ("ram", "ram_percent"),
                               ("disk", "disk_percent")):
                value = max(0.0, min(100.0, metrics[field]))
                self.metric_labels[key].configure(text=f"{value:.1f}%")
                self.metric_bars[key].set(value / 100.0)
            self.metric_labels["download"].configure(
                text=f"التنزيل: {self._format_rate(metrics['download_bps'])}")
            self.metric_labels["upload"].configure(
                text=f"الرفع: {self._format_rate(metrics['upload_bps'])}")
            self.monitor_timestamp.configure(text=f"آخر تحديث: {metrics['sampled_at']}")
        except Exception as exc:
            self.monitor_status.configure(text=f"تعذر القياس: {exc}", text_color="#C77D35")
            self.stop_monitoring()
            return
        self.monitor_after_id = self.after(1000, self._update_live_metrics)

    def _build_settings(self):
        panel = ctk.CTkFrame(self.content, corner_radius=14, fg_color=("#FFFFFF", "#151F35"))
        panel.grid(row=0, column=0, sticky="new", padx=4, pady=4)
        ctk.CTkLabel(panel, text="المظهر", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(panel, text="يمكنك التبديل بين الوضع الداكن والفاتح من أعلى النافذة.", text_color=("#667085", "#A7B0C0")).pack(anchor="w", padx=18, pady=(0, 18))
        ctk.CTkLabel(panel, text="الخصوصية", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=18, pady=(8, 8))
        ctk.CTkLabel(panel, text="لا يتم حفظ سجل تلقائي في هذه المرحلة. جمع البيانات للقراءة فقط.", text_color=("#667085", "#A7B0C0")).pack(anchor="w", padx=18, pady=(0, 18))

    def _build_coming_soon(self, page):
        panel = ctk.CTkFrame(self.content, corner_radius=16, fg_color=("#FFFFFF", "#151F35"), border_width=1,
                             border_color=("#E4E7EC", "#263149"))
        panel.place(relx=0.5, rely=0.42, anchor="center", relwidth=0.78, relheight=0.42)
        ctk.CTkLabel(panel, text="◌", font=ctk.CTkFont(size=42), text_color="#6C8CFF").pack(pady=(25, 5))
        ctk.CTkLabel(panel, text="هذا القسم قيد التطوير", font=ctk.CTkFont(size=21, weight="bold")).pack(pady=5)
        ctk.CTkLabel(panel, text="لن نعرض قراءات وهمية. سيتم تفعيل هذا القسم بعد إضافة محركه واختباره.",
                     text_color=("#667085", "#A7B0C0"), wraplength=500, justify="center").pack(pady=5)
        ctk.CTkLabel(panel, text=f"القسم: {page}", text_color=("#98A2B3", "#667085"), font=ctk.CTkFont(size=11)).pack(pady=(5, 20))

    def refresh_data(self):
        if hasattr(self, "status_label"):
            self.status_label.configure(text="●  جاري تحديث البيانات...", text_color="#D69E36")
        self.refresh_button_state(False)
        threading.Thread(target=self._collect_worker, daemon=True).start()

    def refresh_button_state(self, enabled):
        # The refresh button remains available; the queue prevents UI blocking.
        pass

    def _collect_worker(self):
        try:
            result = collect_all()
            self.worker_queue.put(("success", result))
        except Exception as exc:
            self.worker_queue.put(("error", str(exc)))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()
                if kind == "success":
                    self.data = payload
                    if self.active_page == "Dashboard":
                        self._update_dashboard_cards()
                    elif self.active_page == "Hardware":
                        self.show_page("Hardware")
                    if hasattr(self, "status_label"):
                        self.status_label.configure(text="●  اكتمل جمع البيانات", text_color="#21A179")
                else:
                    messagebox.showerror("خطأ في جمع البيانات", payload)
                    if hasattr(self, "status_label"):
                        self.status_label.configure(text="●  تعذر جمع بعض البيانات", text_color="#C77D35")
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)


def main():
    parser = argparse.ArgumentParser(description="PC Info Tool 2.0")
    parser.add_argument("--cli", action="store_true", help="Print hardware report as JSON")
    args = parser.parse_args()
    if args.cli:
        run_cli()
    else:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        app = PCInfoApp()
        app.mainloop()


if __name__ == "__main__":
    main()
