from __future__ import annotations

import argparse
import json
import platform
import threading
import queue
from tkinter import filedialog
from dataclasses import asdict
from tkinter import messagebox

import customtkinter as ctk

from monitoring.live_metrics import read_live_metrics, reset_network_baseline
from diagnostics import run_diagnostics
from benchmarking import run_benchmark, save_result, load_history, export_history_csv
from reports import export_html_report, export_json_report

from hardware import (
    collect_system, collect_cpu, collect_ram, collect_gpu,
    collect_motherboard, collect_storage, collect_battery, collect_os,
)

APP_NAME = "PC INFO TOOL"
APP_VERSION = "2.0.0"


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
    """Compact dashboard card with a clear label/value hierarchy."""
    def __init__(self, master, title, value="—", hint="", **kwargs):
        super().__init__(master, corner_radius=16, border_width=1, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.accent = ctk.CTkFrame(self, width=4, corner_radius=3,
                                   fg_color="#5B8CFF")
        self.accent.grid(row=0, column=0, rowspan=3, sticky="nsw", padx=(0, 12), pady=14)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=13)
        body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(body, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#667085", "#A6B2C7"), anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        self.value_label = ctk.CTkLabel(body, text=value,
            font=ctk.CTkFont(size=17, weight="bold"), anchor="w", justify="left",
            wraplength=250)
        self.value_label.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        self.hint_label = ctk.CTkLabel(body, text=hint, font=ctk.CTkFont(size=10),
            text_color=("#98A2B3", "#8492A8"), anchor="w", wraplength=250)
        self.hint_label.grid(row=2, column=0, sticky="w")

    def set_value(self, value, hint=None):
        self.value_label.configure(text=value)
        if hint is not None:
            self.hint_label.configure(text=hint)


class PCInfoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(fg_color=("#F3F6FC", "#090F1D"))
        self.data = {}
        self.worker_queue = queue.Queue()
        self.active_page = "Dashboard"
        self.monitor_running = False
        self.monitor_after_id = None
        self.metric_labels = {}
        self.metric_bars = {}
        self.nav_buttons = {}
        self.diagnostics_report = None
        self.diagnostics_running = False
        self.benchmark_running = False
        self.benchmark_result = None
        self.report_running = False
        self._build_shell()
        self.show_page("Dashboard")
        self.refresh_data()
        self.after(150, self._poll_queue)

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar: restrained dark surface, strong active state, clearer grouping.
        self.sidebar = ctk.CTkFrame(self, width=246, corner_radius=0,
                                    fg_color=("#FFFFFF", "#101A2B"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(25, 28))
        mark = ctk.CTkFrame(brand, width=44, height=44, corner_radius=13,
                            fg_color="#315FEA")
        mark.pack(side="left")
        mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="PC", text_color="#FFFFFF",
                     font=ctk.CTkFont(size=16, weight="bold")).place(relx=.5, rely=.5, anchor="center")
        name_box = ctk.CTkFrame(brand, fg_color="transparent")
        name_box.pack(side="left", padx=11)
        ctk.CTkLabel(name_box, text="PC INFO TOOL",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(name_box, text="SYSTEM • INSIGHTS",
                     text_color=("#8A94A6", "#8291A8"),
                     font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(self.sidebar, text="القائمة الرئيسية", anchor="w",
                     text_color=("#98A2B3", "#71819A"),
                     font=ctk.CTkFont(size=10, weight="bold")).pack(
            fill="x", padx=22, pady=(0, 9))
        nav_items = [
            ("Dashboard", "⌂", "لوحة التحكم"),
            ("Hardware", "▦", "مكونات الجهاز"),
            ("Live Monitor", "◷", "المراقبة المباشرة"),
            ("Diagnostics", "✓", "التشخيص"),
            ("Benchmark", "⌁", "اختبار الأداء"),
            ("History", "◴", "سجل الأداء"),
            ("Reports", "▤", "التقارير"),
        ]
        for key, glyph, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=f"{glyph}     {label}", anchor="w", height=45,
                corner_radius=11, border_spacing=12,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent", text_color=("#475467", "#C6D1E2"),
                hover_color=("#EEF3FF", "#1B2A43"),
                command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", padx=13, pady=3)
            self.nav_buttons[key] = btn

        ctk.CTkFrame(self.sidebar, height=1,
                     fg_color=("#E8ECF3", "#25334A")).pack(
            fill="x", padx=18, pady=(22, 13))
        settings_btn = ctk.CTkButton(
            self.sidebar, text="⚙     الإعدادات", anchor="w", height=43,
            corner_radius=11, border_spacing=12,
            font=ctk.CTkFont(size=12, weight="bold"), fg_color="transparent",
            text_color=("#475467", "#C6D1E2"), hover_color=("#EEF3FF", "#1B2A43"),
            command=lambda: self.show_page("Settings"))
        settings_btn.pack(fill="x", padx=13)

        footer = ctk.CTkFrame(self.sidebar, corner_radius=12,
                              fg_color=("#F4F6FA", "#17243A"))
        footer.pack(side="bottom", fill="x", padx=14, pady=16)
        ctk.CTkLabel(footer, text="●  يعمل محلياً على جهازك",
                     text_color="#24A47A", font=ctk.CTkFont(size=10, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(footer, text="PC Info Tool 2.0  •  Phase 9",
                     text_color=("#8A94A6", "#8190A7"),
                     font=ctk.CTkFont(size=9)).pack(anchor="w", padx=12, pady=(0, 10))

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.main, corner_radius=16,
                           fg_color=("#FFFFFF", "#111C30"), border_width=1,
                           border_color=("#E6EAF1", "#202E45"))
        top.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        top.grid_columnconfigure(0, weight=1)
        title_box = ctk.CTkFrame(top, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=20, pady=14)
        self.page_title = ctk.CTkLabel(title_box, text="لوحة التحكم",
            font=ctk.CTkFont(size=23, weight="bold"))
        self.page_title.pack(anchor="w")
        self.page_subtitle = ctk.CTkLabel(title_box,
            text="نظرة عامة على حالة ومكونات جهازك",
            text_color=("#7B8799", "#91A0B6"), font=ctk.CTkFont(size=11))
        self.page_subtitle.pack(anchor="w", pady=(3, 0))

        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=16)
        self.refresh_btn = ctk.CTkButton(actions, text="↻  تحديث البيانات",
            width=142, height=37, corner_radius=10, font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#315FEA", hover_color="#244DC6", command=self.refresh_data)
        self.refresh_btn.pack(side="left", padx=(0, 10))
        self.mode_switch = ctk.CTkSegmentedButton(actions, values=["Dark", "Light"],
            width=118, height=34, corner_radius=9, command=self.change_mode)
        self.mode_switch.set("Dark")
        self.mode_switch.pack(side="left")

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
            "Diagnostics": ("تشخيص الجهاز", "فحوصات منظمة مع توضيح الأدلة والنتائج"),
            "Benchmark": ("اختبار الأداء", "قياس تقريبي لأداء المعالج والذاكرة والقرص"),
            "History": ("سجل الأداء", "الرجوع إلى نتائج الاختبارات السابقة وتصديرها"),
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
        elif page == "Diagnostics":
            self._build_diagnostics()
        elif page == "Benchmark":
            self._build_benchmark()
        elif page == "History":
            self._build_history()
        elif page == "Reports":
            self._build_reports()
        elif page == "Settings":
            self._build_settings()
        else:
            self._build_coming_soon(page)

    def _build_dashboard(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure((0, 1, 2), weight=1, uniform="dashboard")

        hero = ctk.CTkFrame(wrap, corner_radius=19,
            fg_color=("#FFFFFF", "#14223A"), border_width=1,
            border_color=("#E3EAF5", "#263A59"))
        hero.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="SYSTEM OVERVIEW  /  نظرة عامة",
            text_color=("#315FEA", "#8EABFF"),
            font=ctk.CTkFont(size=10, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=22, pady=(18, 5))
        ctk.CTkLabel(hero, text="كل تفاصيل جهازك. في مكان واحد.",
            font=ctk.CTkFont(size=21, weight="bold")).grid(
                row=1, column=0, sticky="w", padx=22, pady=(0, 4))
        ctk.CTkLabel(hero,
            text="استعرض المكونات، راقب استهلاك الموارد، وشغّل أدوات التشخيص والأداء.",
            text_color=("#667085", "#A7B5C9"), font=ctk.CTkFont(size=11)).grid(
                row=2, column=0, sticky="w", padx=22, pady=(0, 18))
        self.status_label = ctk.CTkLabel(hero, text="●  جارٍ تجهيز البيانات...",
            text_color="#D69E36", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=("#FFF7E6", "#3A3020"), corner_radius=9)
        self.status_label.grid(row=0, column=1, rowspan=3, padx=22, pady=18, ipadx=10, ipady=7)

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
            card = InfoCard(wrap, title, value, hint,
                fg_color=("#FFFFFF", "#111C30"),
                border_color=("#E5EAF2", "#22324C"))
            card.grid(row=1 + index // 3, column=index % 3,
                      sticky="nsew", padx=5, pady=5)
            self.cards[key] = card

        note = ctk.CTkFrame(wrap, corner_radius=14,
            fg_color=("#EDF3FF", "#142642"), border_width=1,
            border_color=("#DCE7FF", "#243D62"))
        note.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=(14, 5))
        ctk.CTkLabel(note, text="خصوصيتك أولاً",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#3156C8", "#AFC2FF")).pack(anchor="w", padx=16, pady=(12, 3))
        ctk.CTkLabel(note,
            text="تُجمع معلومات العتاد محلياً. لا تُرسل بيانات جهازك إلى خادم خارجي.",
            justify="left", wraplength=800,
            text_color=("#475467", "#B8C4D9"),
            font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16, pady=(0, 12))
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


    def _build_diagnostics(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)

        intro = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#FFFFFF", "#151F35"),
                             border_width=1, border_color=("#E4E7EC", "#263149"))
        intro.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 12))
        intro.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(intro, text="فحص أولي لحالة الجهاز", font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(15, 4))
        ctk.CTkLabel(intro, text="فحوصات قراءة فقط للمعالج والذاكرة والتخزين والشبكة والبطارية.",
                     text_color=("#667085", "#A7B0C0")).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 12))
        self.diagnostics_button = ctk.CTkButton(intro, text="▶ بدء الفحص", width=135,
                                                command=self.start_diagnostics)
        self.diagnostics_button.grid(row=0, column=1, rowspan=2, padx=18)
        self.diagnostics_summary = ctk.CTkLabel(wrap, text="لم يتم إجراء فحص بعد.",
                                                font=ctk.CTkFont(size=13, weight="bold"))
        self.diagnostics_summary.grid(row=1, column=0, sticky="w", padx=8, pady=(2, 8))
        self.diagnostics_results = ctk.CTkFrame(wrap, fg_color="transparent")
        self.diagnostics_results.grid(row=2, column=0, sticky="ew")
        self.diagnostics_results.grid_columnconfigure(0, weight=1)
        self.diagnostics_footer = ctk.CTkLabel(
            wrap, text="الفحص إرشادي ولا يستبدل أدوات اختبار العتاد المتخصصة.",
            wraplength=850, justify="left", text_color=("#667085", "#A7B0C0"))
        self.diagnostics_footer.grid(row=3, column=0, sticky="w", padx=8, pady=12)
        if self.diagnostics_report:
            self._render_diagnostics(self.diagnostics_report)

    def start_diagnostics(self):
        if self.diagnostics_running:
            return
        self.diagnostics_running = True
        self.diagnostics_button.configure(state="disabled", text="جارٍ الفحص...")
        self.diagnostics_summary.configure(text="جارٍ تنفيذ الفحوصات...")
        threading.Thread(target=self._diagnostics_worker, daemon=True).start()

    def _diagnostics_worker(self):
        try:
            self.worker_queue.put(("diagnostics_success", run_diagnostics()))
        except Exception as exc:
            self.worker_queue.put(("diagnostics_error", str(exc)))

    def _render_diagnostics(self, report):
        for child in self.diagnostics_results.winfo_children():
            child.destroy()
        counts = report.get("counts", {})
        summary = (f"اكتمل الفحص: {counts.get('good', 0)} سليم | "
                   f"{counts.get('warning', 0)} تحذير | "
                   f"{counts.get('problem', 0)} مشكلة | "
                   f"{counts.get('info', 0)} معلومات")
        self.diagnostics_summary.configure(text=summary + "    •    " + report.get("checked_at", ""))
        palette = {
            "good": ("#EAF7F1", "#17382F", "#16845D", "سليم"),
            "warning": ("#FFF6E5", "#3B3020", "#B7791F", "تحذير"),
            "problem": ("#FDECEC", "#402426", "#C34242", "مشكلة"),
            "info": ("#F2F4F7", "#202B3D", "#667085", "معلومات"),
        }
        for item in report.get("checks", []):
            bg_light, bg_dark, accent, status_text = palette.get(item.get("status"), palette["info"])
            card = ctk.CTkFrame(self.diagnostics_results, corner_radius=12,
                                fg_color=(bg_light, bg_dark), border_width=1,
                                border_color=("#E4E7EC", "#263149"))
            card.pack(fill="x", padx=4, pady=5)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(11, 3))
            ctk.CTkLabel(top, text=item.get("title", "فحص"),
                         font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
            ctk.CTkLabel(top, text=status_text, text_color=accent,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
            ctk.CTkLabel(card, text=item.get("value", "—"), anchor="w", justify="left",
                         font=ctk.CTkFont(size=13, weight="bold"), wraplength=800).pack(
                fill="x", padx=14, pady=2)
            ctk.CTkLabel(card, text=item.get("details", ""), anchor="w", justify="left",
                         text_color=("#475467", "#B8C4D9"), wraplength=850).pack(
                fill="x", padx=14, pady=2)
            ctk.CTkLabel(card, text="المصدر: " + item.get("source", "غير معروف"),
                         text_color=("#667085", "#929BAA"), font=ctk.CTkFont(size=10)).pack(
                anchor="w", padx=14, pady=(3, 10))
        self.diagnostics_footer.configure(text=report.get("disclaimer", ""))

    def _build_benchmark(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        panel = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#FFFFFF", "#151F35"), border_width=1)
        panel.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(panel, text="اختبار أداء مختصر", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=18, pady=(18, 5))
        ctk.CTkLabel(panel, text="يقيس سرعة تنفيذ مهمة CPU، وعمليات ذاكرة محدودة، وقراءة/كتابة ملف مؤقت 8MB ثم حذفه.",
                     text_color=("#667085", "#A7B0C0"), wraplength=800, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        self.benchmark_button = ctk.CTkButton(panel, text="▶ بدء اختبار الأداء", command=self.start_benchmark, width=180)
        self.benchmark_button.pack(anchor="w", padx=18, pady=(0, 14))
        self.benchmark_status = ctk.CTkLabel(wrap, text="لم يتم تنفيذ اختبار بعد.", font=ctk.CTkFont(size=13, weight="bold"))
        self.benchmark_status.grid(row=1, column=0, sticky="w", padx=8, pady=12)
        self.benchmark_results = ctk.CTkFrame(wrap, fg_color="transparent")
        self.benchmark_results.grid(row=2, column=0, sticky="ew")
        self.benchmark_results.grid_columnconfigure((0, 1), weight=1)
        if self.benchmark_result:
            self._render_benchmark(self.benchmark_result)
        ctk.CTkLabel(wrap, text="تنبيه: هذا اختبار داخلي تقريبي وليس بديلاً عن أدوات القياس الاحترافية. النتائج تتأثر بالطاقة والحرارة والبرامج المفتوحة.",
                     wraplength=850, justify="left", text_color=("#667085", "#A7B0C0")).grid(row=3, column=0, sticky="w", padx=8, pady=12)

    def start_benchmark(self):
        if self.benchmark_running:
            return
        self.benchmark_running = True
        self.benchmark_button.configure(state="disabled", text="جارٍ الاختبار...")
        self.benchmark_status.configure(text="يتم قياس الأداء. لا تغلق التطبيق...")
        threading.Thread(target=self._benchmark_worker, daemon=True).start()

    def _benchmark_worker(self):
        try:
            result = run_benchmark()
            save_result(result)
            self.worker_queue.put(("benchmark_success", result))
        except Exception as exc:
            self.worker_queue.put(("benchmark_error", str(exc)))

    def _render_benchmark(self, result):
        for child in self.benchmark_results.winfo_children():
            child.destroy()
        self.benchmark_status.configure(text="اكتمل الاختبار: " + result.get("timestamp", ""))
        specs = [
            ("سرعة CPU", f"{result['cpu_ops_per_second']:,.0f} عملية/ثانية"),
            ("كتابة الذاكرة", f"{result['memory_write_mbs']:,.1f} MB/s"),
            ("قراءة الذاكرة", f"{result['memory_read_mbs']:,.1f} MB/s"),
            ("كتابة القرص", f"{result['disk_write_mbs']:,.1f} MB/s"),
            ("قراءة القرص", f"{result['disk_read_mbs']:,.1f} MB/s"),
            ("الذاكرة المتاحة", f"{result['ram_available_gb']:.2f} GB"),
            ("المساحة الحرة", f"{result['disk_free_gb']:.2f} GB"),
        ]
        for index, (label, value) in enumerate(specs):
            card = ctk.CTkFrame(self.benchmark_results, corner_radius=12, fg_color=("#FFFFFF", "#151F35"), border_width=1)
            card.grid(row=index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(card, text=label, text_color=("#667085", "#A7B0C0")).pack(anchor="w", padx=14, pady=(10, 3))
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=14, pady=(0, 10))
        self.benchmark_button.configure(state="normal", text="↻ إعادة الاختبار")

    def _build_history(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(top, text="تصدير CSV", command=self.export_history).pack(side="left")
        ctk.CTkButton(top, text="تحديث السجل", command=lambda: self.show_page("History"), fg_color="transparent", border_width=1).pack(side="left", padx=8)
        history = list(reversed(load_history()))
        if not history:
            ctk.CTkLabel(wrap, text="لا توجد نتائج محفوظة بعد. نفّذ اختباراً من صفحة اختبار الأداء.",
                         text_color=("#667085", "#A7B0C0")).grid(row=1, column=0, sticky="w", padx=8, pady=15)
            return
        headers = "التاريخ والوقت                 CPU عملية/ثانية        RAM كتابة        Disk كتابة        Disk قراءة"
        ctk.CTkLabel(wrap, text=headers, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        for idx, item in enumerate(history[:50], start=2):
            line = (f"{item.get('timestamp','')}     {item.get('cpu_ops_per_second',0):,.0f}     "
                    f"{item.get('memory_write_mbs',0):.1f} MB/s     {item.get('disk_write_mbs',0):.1f} MB/s     "
                    f"{item.get('disk_read_mbs',0):.1f} MB/s")
            row = ctk.CTkFrame(wrap, corner_radius=8, fg_color=("#FFFFFF", "#151F35"))
            row.grid(row=idx, column=0, sticky="ew", pady=3)
            ctk.CTkLabel(row, text=line, anchor="w", font=ctk.CTkFont(size=11)).pack(fill="x", padx=12, pady=10)

    def export_history(self):
        destination = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="PC_Info_Tool_Benchmark_History.csv")
        if not destination:
            return
        try:
            count = export_history_csv(destination)
            messagebox.showinfo("تصدير السجل", f"تم تصدير {count} نتيجة.")
        except Exception as exc:
            messagebox.showerror("تعذر التصدير", str(exc))

    def _build_reports(self):
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        panel = ctk.CTkFrame(wrap, corner_radius=14, fg_color=("#FFFFFF", "#151F35"),
                             border_width=1, border_color=("#E4E7EC", "#263149"))
        panel.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(panel, text="إنشاء تقرير شامل عن الجهاز", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=18, pady=(18, 6))
        ctk.CTkLabel(panel,
            text="يجمع معلومات العتاد ونتائج التشخيص وسجل الأداء المحفوظ. اختر HTML للعرض والطباعة أو JSON للاستخدام التقني.",
            text_color=("#667085", "#A7B0C0"), wraplength=780, justify="left").pack(
            anchor="w", padx=18, pady=(0, 14))
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.pack(anchor="w", padx=18, pady=(0, 12))
        self.report_html_button = ctk.CTkButton(actions, text="إنشاء تقرير HTML", width=170,
                                                 command=lambda: self.export_report("html"))
        self.report_html_button.pack(side="left", padx=(0, 8))
        self.report_json_button = ctk.CTkButton(actions, text="تصدير JSON", width=140,
                                                 fg_color="transparent", border_width=1,
                                                 command=lambda: self.export_report("json"))
        self.report_json_button.pack(side="left")
        self.report_status = ctk.CTkLabel(panel, text="لم يتم إنشاء تقرير في هذه الجلسة.",
                                           text_color=("#667085", "#A7B0C0"))
        self.report_status.pack(anchor="w", padx=18, pady=(0, 18))
        note = ctk.CTkLabel(wrap,
            text="ملاحظة: إنشاء التقرير يجري جمعاً جديداً للمعلومات وتشخيصاً خفيفاً. قد تستغرق العملية عدة ثوانٍ. لا يتضمن التقرير درجات الحرارة.",
            text_color=("#667085", "#A7B0C0"), wraplength=850, justify="left")
        note.grid(row=1, column=0, sticky="w", padx=8, pady=12)

    def export_report(self, report_format):
        if self.report_running:
            return
        if report_format == "html":
            destination = filedialog.asksaveasfilename(
                defaultextension=".html", filetypes=[("HTML", "*.html")],
                initialfile="PC_Info_Tool_System_Report.html")
        else:
            destination = filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON", "*.json")],
                initialfile="PC_Info_Tool_System_Report.json")
        if not destination:
            return
        self.report_running = True
        self.report_html_button.configure(state="disabled")
        self.report_json_button.configure(state="disabled")
        self.report_status.configure(text="جارٍ جمع المعلومات وإنشاء التقرير...")
        threading.Thread(target=self._report_worker, args=(report_format, destination), daemon=True).start()

    def _report_worker(self, report_format, destination):
        try:
            path = export_html_report(destination) if report_format == "html" else export_json_report(destination)
            self.worker_queue.put(("report_success", (str(path), report_format)))
        except Exception as exc:
            self.worker_queue.put(("report_error", str(exc)))

    def _build_settings(self):
        panel = ctk.CTkFrame(self.content, corner_radius=14, fg_color=("#FFFFFF", "#151F35"))
        panel.grid(row=0, column=0, sticky="new", padx=4, pady=4)
        ctk.CTkLabel(panel, text="المظهر", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(panel, text="يمكنك التبديل بين الوضع الداكن والفاتح من أعلى النافذة.", text_color=("#667085", "#A7B0C0")).pack(anchor="w", padx=18, pady=(0, 18))
        ctk.CTkLabel(panel, text="الخصوصية", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=18, pady=(8, 8))
        ctk.CTkLabel(panel, text="يُحفظ سجل اختبارات الأداء محلياً على الجهاز. لا تُرسل بيانات العتاد أو التقارير إلى خادم خارجي.", text_color=("#667085", "#A7B0C0")).pack(anchor="w", padx=18, pady=(0, 18))

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
                elif kind == "benchmark_success":
                    self.benchmark_result = payload
                    self.benchmark_running = False
                    if self.active_page == "Benchmark":
                        self._render_benchmark(payload)
                elif kind == "benchmark_error":
                    self.benchmark_running = False
                    if self.active_page == "Benchmark":
                        self.benchmark_button.configure(state="normal", text="إعادة المحاولة")
                        self.benchmark_status.configure(text="تعذر الاختبار: " + payload)
                elif kind == "diagnostics_success":
                    self.diagnostics_report = payload
                    self.diagnostics_running = False
                    if self.active_page == "Diagnostics":
                        self._render_diagnostics(payload)
                        self.diagnostics_button.configure(state="normal", text="↻ إعادة الفحص")
                elif kind == "diagnostics_error":
                    self.diagnostics_running = False
                    if self.active_page == "Diagnostics":
                        self.diagnostics_button.configure(state="normal", text="إعادة المحاولة")
                        self.diagnostics_summary.configure(text="تعذر إكمال الفحص: " + payload)
                elif kind == "report_success":
                    self.report_running = False
                    if self.active_page == "Reports" and hasattr(self, "report_status"):
                        self.report_html_button.configure(state="normal")
                        self.report_json_button.configure(state="normal")
                        path, report_format = payload
                        self.report_status.configure(text=f"تم إنشاء التقرير بنجاح: {path}")
                        messagebox.showinfo("التقارير", f"تم حفظ التقرير بنجاح.\n{path}")
                elif kind == "report_error":
                    self.report_running = False
                    if self.active_page == "Reports" and hasattr(self, "report_status"):
                        self.report_html_button.configure(state="normal")
                        self.report_json_button.configure(state="normal")
                        self.report_status.configure(text="تعذر إنشاء التقرير: " + payload)
                        messagebox.showerror("التقارير", payload)
                elif kind == "error":
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
