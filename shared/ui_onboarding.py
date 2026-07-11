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
        ("examples", "path_examples"),
    ):
        widget = widgets.get(name)
        if widget:
            widget.setText(onboarding_text(lang, key))
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
    """Show a compact wizard with action buttons for the beginner path."""

    import qt
    import slicer

    lang = getattr(owner, "_onboardingLanguage", "en")
    dialog = qt.QDialog(slicer.util.mainWindow())
    dialog.setWindowTitle(onboarding_text(lang, "wizard"))
    dialog.setMinimumWidth(620)
    layout = qt.QVBoxLayout(dialog)
    intro = qt.QLabel(
        "Follow these steps in order. You can close this wizard and reopen it from Beginner setup."
        if normalized_language(lang) == "en"
        else "按顺序完成这些步骤。关闭后也可以从“新手设置”重新打开。"
    )
    intro.wordWrap = True
    layout.addWidget(intro)

    steps = [
        ("1. Check Slicer Python", "检查 Slicer Python", lambda: slicer.util.infoDisplay(owner._python_install_target_text())),
        ("2. Choose model assets root", "选择模型权重目录", lambda: owner._install_model_assets_from_environment_dialog(profile="core")),
        ("3. Download / verify model assets", "下载 / 验证模型权重", lambda: owner._on_verify_core_model_assets_clicked()),
        ("4. Scan MRtrix/FSL/FreeSurfer", "扫描 MRtrix/FSL/FreeSurfer", owner._onValidateClicked),
        ("5. Show capability report", "显示可运行能力报告", lambda: owner._update_onboarding_dashboard(getattr(owner, "_lastEnvironmentResult", None))),
    ]
    for english, chinese, callback in steps:
        row = qt.QHBoxLayout()
        label = qt.QLabel(chinese if normalized_language(lang) == "zh" else english)
        label.setMinimumWidth(260)
        button = qt.QPushButton("Run" if normalized_language(lang) == "en" else "执行")
        button.connect("clicked()", callback)
        row.addWidget(label, 1)
        row.addWidget(button)
        layout.addLayout(row)
    close_button = qt.QPushButton("Close" if normalized_language(lang) == "en" else "关闭")
    close_button.connect("clicked()", dialog.accept)
    layout.addWidget(close_button)
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
