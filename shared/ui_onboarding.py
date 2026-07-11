"""Beginner-facing onboarding helpers for the SlicerDDSurfer UI."""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.demo_data import DEMO_SUBJECT_ID, create_synthetic_demo_subject
from shared.user_config import default_user_config_path, load_user_config, update_user_config


LANGUAGE_SETTING = "SlicerDDSurfer/UserSettings/language"
FIRST_RUN_SETTING = "SlicerDDSurfer/UserSettings/firstRunWizardShown"

TRANSLATIONS = {
    "en": {
        "beginner_title": "Beginner setup",
        "beginner_body": (
            "Start here if you are new: run the setup wizard, try a synthetic demo subject, "
            "then check what this computer can run."
        ),
        "wizard": "First-run setup wizard",
        "demo": "Demo / Try with sample data",
        "copy_diag": "Copy diagnostic report",
        "open_config": "Open settings JSON",
        "language": "Language",
        "dashboard_waiting": "Run Check environment dependencies to see what is runnable on this computer.",
        "path_examples": (
            "Examples: Subject root /Users/name/data/sub-01 | Output /Users/name/data/sub-01/outputs | "
            "Model assets /Users/name/SlicerDDSurfer-model-assets | MRtrix bin /opt/mrtrix3/bin"
        ),
        "headline": "SlicerDDSurfer Release Workbench",
        "subtitle": (
            "Prepare one subject root, preflight external dependencies, and run reusable diffusion products "
            "from one monitored pipeline."
        ),
        "choose_input": "<b>1. Choose input</b>",
        "choose_products": "<b>2. Choose products</b>",
        "run": "<b>3. Run</b>",
        "check_env": "Check environment dependencies",
        "preflight_run": "Preflight and run",
    },
    "zh": {
        "beginner_title": "新手设置",
        "beginner_body": "如果你不熟悉环境配置，从这里开始：运行向导、尝试合成样例，然后检查这台电脑能跑哪些功能。",
        "wizard": "首次运行设置向导",
        "demo": "Demo / 我只是想试一下",
        "copy_diag": "复制诊断报告",
        "open_config": "打开设置 JSON",
        "language": "语言",
        "dashboard_waiting": "点击“检查环境依赖”后，这里会显示这台电脑现在能跑什么、还缺什么。",
        "path_examples": (
            "路径示例：Subject root /Users/name/data/sub-01 | Output /Users/name/data/sub-01/outputs | "
            "模型权重 /Users/name/SlicerDDSurfer-model-assets | MRtrix bin /opt/mrtrix3/bin"
        ),
        "headline": "SlicerDDSurfer 运行工作台",
        "subtitle": "准备一个 subject root，检查依赖环境，并从同一个监控流程运行可复用的 dMRI 分析产品。",
        "choose_input": "<b>1. 选择输入</b>",
        "choose_products": "<b>2. 选择要运行的结果</b>",
        "run": "<b>3. 检查并运行</b>",
        "check_env": "检查环境依赖",
        "preflight_run": "预检查并运行",
    },
}


def normalized_language(value: str | None) -> str:
    """Return a supported UI language code."""

    return "zh" if str(value or "").lower().startswith("zh") else "en"


def onboarding_text(language: str, key: str) -> str:
    """Return translated onboarding text with English fallback."""

    lang = normalized_language(language)
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))


def platform_path_examples(language: str, *, system: str | None = None) -> str:
    """Return path examples that match the user's operating system."""

    system_name = (system or platform.system()).lower()
    if system_name.startswith("win"):
        subject = r"C:\Users\name\data\sub-01"
        output = r"C:\Users\name\data\sub-01\outputs"
        models = r"C:\Users\name\SlicerDDSurfer-model-assets"
        mrtrix = r"C:\Tools\MRtrix3\bin"
    elif system_name == "darwin":
        subject = "/Users/name/data/sub-01"
        output = "/Users/name/data/sub-01/outputs"
        models = "/Users/name/Library/Application Support/SlicerDDSurfer/model-assets"
        mrtrix = "/opt/homebrew/bin"
    else:
        subject = "/home/name/data/sub-01"
        output = "/home/name/data/sub-01/outputs"
        models = "/home/name/.local/share/SlicerDDSurfer/model-assets"
        mrtrix = "/opt/mrtrix3/bin"
    if normalized_language(language) == "zh":
        return (
            f"本机路径示例：Subject root {subject} | 输出目录 {output} | "
            f"模型权重 {models} | MRtrix bin {mrtrix}"
        )
    return (
        f"Examples for this computer: Subject root {subject} | Output {output} | "
        f"Model assets {models} | MRtrix bin {mrtrix}"
    )


def capability_dashboard_text(result: Any, *, language: str = "en") -> str:
    """Summarize environment capability for non-technical users."""

    if result is None:
        return onboarding_text(language, "dashboard_waiting")
    runnable = tuple(getattr(result, "runnable_targets", ()) or ())
    blocked = tuple(getattr(result, "blocked_targets", ()) or ())
    statuses = tuple(getattr(result, "statuses", ()) or ())
    missing_by_target: dict[str, list[str]] = {}
    for item in statuses:
        if getattr(item, "status", "") != "missing":
            continue
        label = str(getattr(item, "label", "") or getattr(item, "key", "") or "dependency")
        for target in tuple(getattr(item, "targets", ()) or ()):
            missing_by_target.setdefault(str(target), []).append(label)
    if normalized_language(language) == "zh":
        lines = [
            "你现在可以运行：" + (", ".join(runnable) if runnable else "暂无，需要先补齐输入或依赖"),
        ]
        if blocked:
            lines.append("你还不能运行：")
            for target in blocked:
                reasons = ", ".join(dict.fromkeys(missing_by_target.get(target, [])) or ["缺少依赖或输入"])
                lines.append(f"- {target}: {reasons}")
        else:
            lines.append("没有检测到被阻塞的已选目标。")
        return "\n".join(lines)
    lines = [
        "Runnable now: " + (", ".join(runnable) if runnable else "none yet; add inputs or dependencies first"),
    ]
    if blocked:
        lines.append("Needs setup:")
        for target in blocked:
            reasons = ", ".join(dict.fromkeys(missing_by_target.get(target, [])) or ["missing dependency or input"])
            lines.append(f"- {target}: {reasons}")
    else:
        lines.append("No selected targets are blocked.")
    return "\n".join(lines)


def diagnostic_report_text(owner: Any) -> str:
    """Build a compact report users can paste into an issue or support message."""

    node = getattr(owner, "_parameterNode", None)
    settings_payload = {}
    for key in (
        "model_assets_dir",
        "mrtrix_bin_dir",
        "preprocessing_fsl_bin_dir",
        "postprocess_freesurfer_home",
        "tract_querier_root",
        "wma_root",
        "tractcloud_root",
    ):
        try:
            settings_payload[key] = owner._read_environment_path_setting(key)
        except Exception:
            settings_payload[key] = ""
    result = getattr(owner, "_lastEnvironmentResult", None)
    missing = []
    if result is not None:
        for item in tuple(getattr(result, "statuses", ()) or ()):
            if getattr(item, "status", "") == "missing":
                missing.append(
                    {
                        "key": getattr(item, "key", ""),
                        "label": getattr(item, "label", ""),
                        "targets": list(getattr(item, "targets", ()) or ()),
                    }
                )
    log_tail = ""
    log_widget = getattr(getattr(owner, "ui", None), "logPlainTextEdit", None)
    if log_widget is not None:
        try:
            log_tail = "\n".join(str(log_widget.toPlainText()).splitlines()[-80:])
        except Exception:
            log_tail = ""
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "platform": platform.platform(),
        "python": sys.executable,
        "user_config_path": default_user_config_path().expanduser().as_posix(),
        "slicer_version": getattr(getattr(sys.modules.get("slicer"), "app", None), "applicationVersion", "unknown"),
        "subject_id": getattr(node, "subjectId", "") if node else "",
        "subject_root": getattr(node, "inputDirectory", "") if node else "",
        "output_directory": getattr(node, "outputDirectory", "") if node else "",
        "external_paths": settings_payload,
        "runnable_targets": list(getattr(result, "runnable_targets", ()) or ()) if result is not None else [],
        "blocked_targets": list(getattr(result, "blocked_targets", ()) or ()) if result is not None else [],
        "missing_dependencies": missing,
        "log_tail": log_tail,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


def install_onboarding_panel(owner: Any, parent_layout: Any) -> None:
    """Install beginner-first controls into the existing Slicer module UI."""

    import qt

    panel = qt.QFrame()
    panel.setObjectName("onboardingPanel")
    panel.setStyleSheet(
        "QFrame#onboardingPanel { background: #F7FBF8; border: 1px solid #CFE4D5; "
        "border-radius: 10px; padding: 10px; }"
    )
    layout = qt.QVBoxLayout(panel)

    top = qt.QHBoxLayout()
    title = qt.QLabel()
    title.setObjectName("onboardingTitleLabel")
    title.setStyleSheet("QLabel { color: #173D2A; font-size: 15px; font-weight: 800; }")
    top.addWidget(title, 1)
    language_label = qt.QLabel()
    language_label.setObjectName("onboardingLanguageLabel")
    language_combo = qt.QComboBox()
    language_combo.addItem("English", "en")
    language_combo.addItem("中文", "zh")
    top.addWidget(language_label)
    top.addWidget(language_combo)
    layout.addLayout(top)

    body = qt.QLabel()
    body.setObjectName("onboardingBodyLabel")
    body.wordWrap = True
    body.setStyleSheet("QLabel { color: #426154; }")
    layout.addWidget(body)

    buttons = qt.QHBoxLayout()
    wizard_button = qt.QPushButton()
    demo_button = qt.QPushButton()
    diagnostic_button = qt.QPushButton()
    config_button = qt.QPushButton()
    buttons.addWidget(wizard_button)
    buttons.addWidget(demo_button)
    buttons.addWidget(diagnostic_button)
    buttons.addWidget(config_button)
    buttons.addStretch(1)
    layout.addLayout(buttons)

    dashboard = qt.QLabel()
    dashboard.setObjectName("capabilityDashboardLabel")
    dashboard.wordWrap = True
    dashboard.setStyleSheet(
        "QLabel { background: #FFFFFF; border: 1px solid #DCE8E0; border-radius: 8px; "
        "color: #244034; padding: 8px; }"
    )
    layout.addWidget(dashboard)

    examples = qt.QLabel()
    examples.setObjectName("pathExamplesLabel")
    examples.wordWrap = True
    examples.setStyleSheet("QLabel { color: #6B7D74; font-size: 11px; }")
    layout.addWidget(examples)

    owner._onboardingWidgets = {
        "panel": panel,
        "title": title,
        "language_label": language_label,
        "language_combo": language_combo,
        "body": body,
        "wizard_button": wizard_button,
        "demo_button": demo_button,
        "diagnostic_button": diagnostic_button,
        "config_button": config_button,
        "dashboard": dashboard,
        "examples": examples,
    }

    language_combo.currentIndexChanged.connect(owner._on_onboarding_language_changed)
    wizard_button.connect("clicked()", owner._on_show_first_run_wizard_clicked)
    demo_button.connect("clicked()", owner._on_try_demo_clicked)
    diagnostic_button.connect("clicked()", owner._on_copy_diagnostic_report_clicked)
    config_button.connect("clicked()", owner._on_open_user_config_clicked)

    try:
        parent_layout.insertWidget(0, panel)
    except Exception:
        parent_layout.addWidget(panel)


def apply_onboarding_language(owner: Any, language: str) -> None:
    """Apply translated labels to the beginner-facing and primary workflow UI."""

    lang = normalized_language(language)
    widgets = getattr(owner, "_onboardingWidgets", {}) or {}
    for name, key in (
        ("title", "beginner_title"),
        ("language_label", "language"),
        ("body", "beginner_body"),
        ("wizard_button", "wizard"),
        ("demo_button", "demo"),
        ("diagnostic_button", "copy_diag"),
        ("config_button", "open_config"),
    ):
        widget = widgets.get(name)
        if widget:
            widget.setText(onboarding_text(lang, key))
    examples = widgets.get("examples")
    if examples:
        examples.setText(platform_path_examples(lang))
    combo = widgets.get("language_combo")
    if combo:
        index = combo.findData(lang)
        if index >= 0 and combo.currentIndex != index:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
    primary = {
        "headlineLabel": "headline",
        "subtitleLabel": "subtitle",
        "configurationSectionLabel": "choose_input",
        "targetsSectionLabel": "choose_products",
        "runStepSectionLabel": "run",
        "validateButton": "check_env",
        "runSelectedButton": "preflight_run",
    }
    ui = getattr(owner, "ui", None)
    for widget_name, key in primary.items():
        widget = getattr(ui, widget_name, None)
        if widget:
            widget.setText(onboarding_text(lang, key))
    dashboard = widgets.get("dashboard")
    if dashboard:
        dashboard.setText(capability_dashboard_text(getattr(owner, "_lastEnvironmentResult", None), language=lang))


def maybe_show_first_run_wizard(owner: Any) -> None:
    """Show the first-run wizard once per user settings profile."""

    import qt
    import slicer

    if os.environ.get("SLICERDDSURFER_DISABLE_FIRST_RUN_WIZARD") == "1":
        return
    settings = slicer.app.userSettings()
    try:
        config = load_user_config()
        shown_in_json = bool(config.get("ui", {}).get("first_run_wizard_shown"))
    except Exception:
        shown_in_json = False
    if shown_in_json or str(settings.value(FIRST_RUN_SETTING, "") or "") == "1":
        return
    settings.setValue(FIRST_RUN_SETTING, "1")
    try:
        update_user_config({"ui": {"first_run_wizard_shown": True}})
    except Exception:
        pass
    qt.QTimer.singleShot(1200, owner._on_show_first_run_wizard_clicked)


def show_first_run_wizard(owner: Any) -> None:
    """Show a stateful setup checklist for the beginner path."""

    import qt
    import slicer

    lang = getattr(owner, "_onboardingLanguage", "en")
    dialog = qt.QDialog(slicer.util.mainWindow())
    dialog.setObjectName("firstRunSetupWizardDialog")
    dialog.setWindowTitle(onboarding_text(lang, "wizard"))
    dialog.setMinimumWidth(760)
    layout = qt.QVBoxLayout(dialog)
    is_zh = normalized_language(lang) == "zh"
    copy = {
        "intro": (
            "按顺序执行并查看每一步的状态。外部软件只在相应分析中需要，扫描后即使有可选项缺失，也可以先运行可用功能。"
            if is_zh
            else "Work through the steps and review each status. External tools are needed only for their related analyses; you can run available features even when optional items are missing."
        ),
        "progress": "设置进度" if is_zh else "Setup progress",
        "pending": "尚未执行" if is_zh else "Not run yet",
        "working": "正在执行..." if is_zh else "Working...",
        "ready": "已完成" if is_zh else "Ready",
        "failed": "需要处理" if is_zh else "Needs attention",
        "python_title": "1. 确认 Slicer Python" if is_zh else "1. Confirm Slicer Python",
        "python_body": "Python 包会安装到当前 Slicer 自带的 Python，不会改动系统 Python。" if is_zh else "Python packages are installed into this Slicer Python, not the system Python.",
        "python_action": "显示 Python 位置" if is_zh else "Show Python location",
        "root_title": "2. 选择模型权重目录" if is_zh else "2. Choose model asset folder",
        "root_body": "权重属于用户数据，应放在插件目录之外；选择一次后会自动记住。" if is_zh else "Weights are user data and should live outside the extension folder. This choice is remembered.",
        "root_action": "选择目录" if is_zh else "Choose folder",
        "models_title": "3. 下载并校验核心模型" if is_zh else "3. Download and verify core models",
        "models_body": "显示当前文件和进度；取消后保留部分文件，下次可继续下载。" if is_zh else "Shows the current file and progress. Cancelling keeps partial files so the next attempt can resume.",
        "models_action": "下载 / 继续下载" if is_zh else "Download / resume",
        "scan_title": "4. 扫描本机依赖" if is_zh else "4. Scan this computer",
        "scan_body": "自动搜索常见的 Windows、macOS 或 Linux 路径，并说明哪些功能已经可运行。" if is_zh else "Searches common Windows, macOS or Linux locations and reports which features can run now.",
        "scan_action": "开始扫描" if is_zh else "Scan now",
        "report_title": "5. 查看可运行能力报告" if is_zh else "5. Review capability report",
        "report_body": "报告会区分现在可运行的功能与仍需配置的可选功能。" if is_zh else "The report separates features that run now from optional features that still need setup.",
        "report_action": "显示报告" if is_zh else "Show report",
        "demo": "直接运行轻量示例" if is_zh else "Run lightweight demo",
        "guide": "打开本系统安装指南" if is_zh else "Open setup guide for this OS",
        "close": "关闭" if is_zh else "Close",
        "cancelled": "未选择目录；原设置没有改变。" if is_zh else "No folder selected; existing settings were unchanged.",
        "download_failed": "下载未完成。可以再次点击以继续。" if is_zh else "Download is incomplete. Click again to resume.",
        "scan_failed": "扫描没有完成；请复制诊断报告后重试。" if is_zh else "The scan did not complete. Copy the diagnostic report and retry.",
        "report_missing": "请先执行依赖扫描。" if is_zh else "Run the dependency scan first.",
    }
    intro = qt.QLabel(copy["intro"])
    intro.wordWrap = True
    intro.setStyleSheet("QLabel { color: #3E5B4A; padding: 4px 2px 8px 2px; }")
    layout.addWidget(intro)

    progress_label = qt.QLabel(f"{copy['progress']}: 0 / 5")
    progress_label.setObjectName("firstRunWizardProgressLabel")
    progress_label.setStyleSheet("QLabel { color: #173D2A; font-weight: 700; padding-bottom: 4px; }")
    layout.addWidget(progress_label)

    scroll = qt.QScrollArea()
    scroll.setObjectName("firstRunWizardScrollArea")
    scroll.setWidgetResizable(True)
    scroll.setMinimumHeight(430)
    steps_container = qt.QWidget()
    steps_layout = qt.QVBoxLayout(steps_container)
    steps_layout.setContentsMargins(2, 2, 2, 2)
    scroll.setWidget(steps_container)
    layout.addWidget(scroll, 1)

    def python_action() -> tuple[bool, str]:
        target = str(owner._python_install_target_text())
        slicer.util.infoDisplay(target, windowTitle=copy["python_title"], parent=dialog)
        return True, target

    def root_action() -> tuple[bool, str]:
        root = owner._choose_model_assets_root()
        return (root is not None), (str(root) if root is not None else copy["cancelled"])

    def models_action() -> tuple[bool, str]:
        ok = bool(owner._install_model_assets_from_environment_dialog(profile="core", prompt_for_root=False))
        if not ok:
            return False, copy["download_failed"]
        _, _, verification = owner._model_asset_verification("core", check_hashes=False)
        return True, owner._format_model_asset_status_line("core", verification)

    def scan_action() -> tuple[bool, str]:
        result = owner._onValidateClicked()
        if result is None:
            return False, copy["scan_failed"]
        runnable = len(tuple(getattr(result, "runnable_targets", ()) or ()))
        blocked = len(tuple(getattr(result, "blocked_targets", ()) or ()))
        detail = f"{runnable} runnable; {blocked} need setup"
        if is_zh:
            detail = f"{runnable} 项可运行；{blocked} 项仍需配置"
        return True, detail

    def report_action() -> tuple[bool, str]:
        result = getattr(owner, "_lastEnvironmentResult", None)
        if result is None:
            return False, copy["report_missing"]
        report = capability_dashboard_text(result, language=lang)
        owner._update_onboarding_dashboard(result)
        slicer.util.infoDisplay(report, windowTitle=copy["report_title"], parent=dialog)
        return True, ("报告已显示。" if is_zh else "Capability report displayed.")

    steps = [
        (copy["python_title"], copy["python_body"], copy["python_action"], python_action),
        (copy["root_title"], copy["root_body"], copy["root_action"], root_action),
        (copy["models_title"], copy["models_body"], copy["models_action"], models_action),
        (copy["scan_title"], copy["scan_body"], copy["scan_action"], scan_action),
        (copy["report_title"], copy["report_body"], copy["report_action"], report_action),
    ]
    status_labels = []
    action_buttons = []
    step_frames = []
    completed_steps: set[int] = set()

    def set_step_status(index: int, state: str, detail: str) -> None:
        label = status_labels[index]
        prefix = copy["ready"] if state == "ready" else copy["failed"] if state == "failed" else copy["working"] if state == "working" else copy["pending"]
        label.setText(f"{prefix}: {detail}" if detail else prefix)
        colors = {
            "ready": ("#EAF6EE", "#26643D"),
            "failed": ("#FFF3E8", "#9A4B13"),
            "working": ("#EAF2F8", "#285A78"),
            "pending": ("#F3F5F4", "#64736B"),
        }
        background, foreground = colors.get(state, colors["pending"])
        label.setStyleSheet(
            f"QLabel {{ background: {background}; color: {foreground}; border-radius: 5px; padding: 4px 7px; }}"
        )
        if state == "ready":
            completed_steps.add(index)
        elif index in completed_steps:
            completed_steps.remove(index)
        progress_label.setText(f"{copy['progress']}: {len(completed_steps)} / {len(steps)}")

    def run_step(index: int, callback) -> None:
        set_step_status(index, "working", "")
        slicer.app.processEvents()
        try:
            ok, detail = callback()
        except Exception as exc:
            ok, detail = False, str(exc)
        set_step_status(index, "ready" if ok else "failed", detail)

    for index, (title_text, body_text, action_text, callback) in enumerate(steps):
        frame = qt.QFrame()
        frame.setObjectName(f"firstRunWizardStep{index + 1}")
        frame.setStyleSheet("QFrame { background: #FFFFFF; border: 1px solid #DCE8E0; border-radius: 8px; }")
        row = qt.QGridLayout(frame)
        title = qt.QLabel(f"<b>{title_text}</b>")
        body = qt.QLabel(body_text)
        body.wordWrap = True
        body.setStyleSheet("QLabel { color: #51665A; border: none; }")
        status = qt.QLabel(copy["pending"])
        status.setObjectName(f"firstRunWizardStatus{index + 1}")
        status.setWordWrap(True)
        button = qt.QPushButton(action_text)
        button.setObjectName(f"firstRunWizardAction{index + 1}")
        button.setMinimumWidth(150)
        button.connect("clicked()", lambda step=index, action=callback: run_step(step, action))
        row.addWidget(title, 0, 0)
        row.addWidget(button, 0, 1, 2, 1)
        row.addWidget(body, 1, 0)
        row.addWidget(status, 2, 0, 1, 2)
        steps_layout.addWidget(frame)
        step_frames.append(frame)
        action_buttons.append(button)
        status_labels.append(status)
        set_step_status(index, "pending", "")
    steps_layout.addStretch(1)

    set_step_status(0, "ready", str(owner._python_install_target_text()))
    configured_root = str(owner._read_environment_path_setting("model_assets_dir") or "").strip()
    if configured_root:
        set_step_status(1, "ready", configured_root)
    try:
        _, _, existing = owner._model_asset_verification("core", check_hashes=False)
        if existing.get("ok"):
            set_step_status(2, "ready", owner._format_model_asset_status_line("core", existing))
    except Exception:
        pass
    existing_result = getattr(owner, "_lastEnvironmentResult", None)
    if existing_result is not None:
        runnable = len(tuple(getattr(existing_result, "runnable_targets", ()) or ()))
        blocked = len(tuple(getattr(existing_result, "blocked_targets", ()) or ()))
        existing_detail = f"{runnable} runnable; {blocked} need setup"
        if is_zh:
            existing_detail = f"{runnable} 项可运行；{blocked} 项仍需配置"
        set_step_status(3, "ready", existing_detail)

    footer = qt.QHBoxLayout()
    guide_button = qt.QPushButton(copy["guide"])
    system_name = platform.system()
    guide_name = "WINDOWS.md" if system_name == "Windows" else "MACOS.md" if system_name == "Darwin" else "LINUX_HPC.md"
    guide_button.connect(
        "clicked()",
        lambda: owner._open_local_path(
            Path(__file__).resolve().parent.parent / "docs" / "setup" / guide_name,
            missing_message=f"docs/setup/{guide_name} is unavailable.",
        ),
    )
    demo_button = qt.QPushButton(copy["demo"])
    demo_button.connect("clicked()", lambda: (dialog.accept(), owner._on_try_demo_clicked()))
    close_button = qt.QPushButton(copy["close"])
    close_button.connect("clicked()", dialog.accept)
    footer.addWidget(guide_button)
    footer.addWidget(demo_button)
    footer.addStretch(1)
    footer.addWidget(close_button)
    layout.addLayout(footer)
    owner._firstRunWizardWidgets = {
        "dialog": dialog,
        "progress": progress_label,
        "scroll": scroll,
        "step_frames": tuple(step_frames),
        "status_labels": tuple(status_labels),
        "action_buttons": tuple(action_buttons),
    }
    dialog.exec_()


def prepare_demo_for_owner(owner: Any) -> Path:
    """Create a synthetic demo subject and configure the UI for light testing."""

    import slicer

    demo_root = Path(str(slicer.app.temporaryPath)) / "SlicerDDSurfer" / "demo"
    subject_root = create_synthetic_demo_subject(demo_root, subject_id=DEMO_SUBJECT_ID)
    node = getattr(owner, "_parameterNode", None)
    if node:
        with slicer.util.NodeModify(node):
            node.subjectId = DEMO_SUBJECT_ID
            node.inputDirectory = subject_root.as_posix()
            node.outputDirectory = (subject_root / "outputs").as_posix()
            node.targetPreprocessing = False
            node.targetSurface = False
            node.targetParcellation = False
            node.targetSegmentation = False
            node.targetMicrostructure = True
            node.targetTractography = True
            node.targetBundles = False
            node.targetConnectome = False
            node.orchestrationTractographyBackend = "dti_det"
            node.orchestrationMicrostructureStages = "dti"
            node.orchestrationRunName = "Demo"
        owner._checkCanApply()
    owner.appendLog(f"[Demo] Synthetic demo subject prepared: {subject_root}")
    return subject_root
