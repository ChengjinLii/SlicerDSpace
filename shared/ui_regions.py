"""Advanced-only regional analysis using completed, explicitly selected run products."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
import uuid


TEXT = {
    "en": dict(
        title="Regional analysis (optional)",
        source="Source run manifest",
        latest="Use latest run",
        atlas="Atlas override (optional)",
        lut="Custom atlas LUT (optional)",
        inspect="Load regions and available results",
        search="Search name, hemisphere or label ID",
        select="Select visible",
        clear="Clear selection",
        metrics="Microstructure statistics",
        tracts="ROI streamline selection",
        graph="Regional connectivity",
        output="Output folder (optional)",
        run="Analyze selected regions",
        empty="Select a completed subject run. No models are refitted.",
        rules=[
            "Pass through any selected region",
            "Pass through all selected regions",
            "At least one endpoint in selection",
            "Both endpoints in selection",
        ],
        note="Uses full quantitative files, not display previews. Invalid fits stay excluded. ROI tracks are a geometric subset, not automatically identified anatomical bundles.",
    ),
    "zh": dict(
        title="脑区分析（可选）",
        source="来源运行记录",
        latest="使用最近一次运行",
        atlas="替代分区图（可选）",
        lut="自定义分区 LUT（可选）",
        inspect="读取脑区与可用结果",
        search="搜索脑区名称、左右半球或标签 ID",
        select="勾选可见脑区",
        clear="清空选择",
        metrics="微结构统计",
        tracts="选区相关流线",
        graph="脑区连接分析",
        output="输出文件夹（可选）",
        run="分析所选脑区",
        empty="选择已完成的单被试运行记录；不会重新拟合模型。",
        rules=["经过任一所选脑区", "经过全部所选脑区", "至少一个端点在选区内", "两个端点都在选区内"],
        note="使用完整定量文件，不使用显示预览；无效拟合仍排除。选区流线是几何筛选结果，不自动等同于解剖束识别。",
    ),
}


def install_region_panel(owner):
    import ctk
    import qt

    panel = ctk.ctkCollapsibleButton(owner._advancedSettingsPanel)
    panel.objectName = "regionalAnalysisPanel"
    panel.collapsed = True
    panel.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Maximum)
    layout = qt.QVBoxLayout(panel)
    form = qt.QFormLayout()
    form.setFieldGrowthPolicy(qt.QFormLayout.AllNonFixedFieldsGrow)
    layout.addLayout(form)
    controls = dict(panel=panel, labels={})
    for key in ("source", "atlas", "lut", "output"):
        path = ctk.ctkPathLineEdit()
        path.setSizePolicy(qt.QSizePolicy.Ignored, qt.QSizePolicy.Fixed)
        path.filters = ctk.ctkPathLineEdit.Dirs if key == "output" else ctk.ctkPathLineEdit.Files
        label = qt.QLabel()
        controls[key] = path
        controls["labels"][key] = label
        form.addRow(label, path)
    row = qt.QHBoxLayout()
    for key in ("latest", "inspect"):
        button = qt.QPushButton()
        controls[key] = button
        row.addWidget(button)
    layout.addLayout(row)
    search = qt.QLineEdit()
    controls["search"] = search
    layout.addWidget(search)
    regions = qt.QListWidget()
    regions.objectName = "regionalLabelsList"
    regions.setMaximumHeight(180)
    regions.setMinimumHeight(100)
    controls["regions"] = regions
    layout.addWidget(regions)
    row = qt.QHBoxLayout()
    for key in ("select", "clear"):
        button = qt.QPushButton()
        controls[key] = button
        row.addWidget(button)
    layout.addLayout(row)
    for key in ("metrics", "tracts", "graph"):
        box = qt.QCheckBox()
        box.enabled = False
        controls[key] = box
        layout.addWidget(box)
    metric_list = qt.QListWidget()
    metric_list.objectName = "regionalMetricsList"
    metric_list.setMaximumHeight(100)
    metric_list.enabled = False
    controls["metric_list"] = metric_list
    layout.insertWidget(layout.indexOf(controls["tracts"]), metric_list)
    for key in ("tract_source", "rule", "graph_source"):
        combo = qt.QComboBox()
        controls[key] = combo
        if key == "graph_source":
            layout.addWidget(combo)
        else:
            layout.insertWidget(layout.indexOf(controls["graph"]), combo)
    for index, key in enumerate(("through_any", "through_all", "endpoint_any", "endpoint_both")):
        controls["rule"].addItem(key, key)
    note = qt.QLabel()
    note.wordWrap = True
    controls["note"] = note
    layout.addWidget(note)
    button = qt.QPushButton()
    button.objectName = "runRegionalAnalysisButton"
    button.enabled = False
    controls["run"] = button
    layout.addWidget(button)
    status = qt.QLabel()
    status.wordWrap = True
    controls["status"] = status
    layout.addWidget(status)
    owner._regionWidgets = controls
    owner._regionCatalog = None
    owner._advancedSettingsPanel.layout().insertWidget(3, panel)
    controls["latest"].clicked.connect(lambda: use_latest_run(owner))
    controls["inspect"].clicked.connect(lambda: inspect_regions(owner))
    controls["run"].clicked.connect(lambda: analyze_regions(owner))
    controls["select"].clicked.connect(lambda: set_checks(owner, True))
    controls["clear"].clicked.connect(lambda: set_checks(owner, False))
    controls["search"].textChanged.connect(lambda value: filter_regions(owner, value))
    for key in ("source", "atlas", "lut"):
        controls[key].currentPathChanged.connect(lambda *_: invalidate_catalog(owner))
    controls["metrics"].toggled.connect(lambda enabled: metric_list.setEnabled(enabled))
    controls["tracts"].toggled.connect(lambda enabled: _tract_enabled(owner, enabled))
    controls["graph"].toggled.connect(lambda enabled: controls["graph_source"].setEnabled(enabled))
    panel.connect("contentsCollapsed(bool)", lambda collapsed: _expanded(owner, collapsed))
    apply_region_language(owner, getattr(owner, "_onboardingLanguage", "en"))
    _tract_enabled(owner, False)
    controls["graph_source"].enabled = False


def _count(widget):
    value = widget.count
    return value() if callable(value) else int(value)


def _paths(owner):
    return tuple(str(owner._regionWidgets[key].currentPath or "").strip() for key in ("source", "atlas", "lut"))


def _status(owner, text, error=False):
    label = owner._regionWidgets["status"]
    label.text = text
    label.setStyleSheet("color: #B3261E;" if error else "color: #52616B;")


def _expanded(owner, collapsed):
    import qt

    if not collapsed and not _paths(owner)[0]:
        use_latest_run(owner)
    root = owner._uiWidget

    def fit():
        root.layout().invalidate()
        root.layout().activate()
        root.resize(root.width, root.minimumSizeHint.height())

    qt.QTimer.singleShot(0, fit)


def _tract_enabled(owner, enabled):
    for key in ("tract_source", "rule"):
        owner._regionWidgets[key].enabled = enabled


def invalidate_catalog(owner):
    owner._regionCatalog = None
    owner._regionWidgets["run"].enabled = False
    for key in ("metrics", "tracts", "graph"):
        owner._regionWidgets[key].checked = False
        owner._regionWidgets[key].enabled = False
    _status(owner, "Inputs changed; reload regions / 输入已改变，请重新读取脑区")


def use_latest_run(owner):
    path = getattr(owner, "_latestResultManifestPath", None)
    if path:
        owner._regionWidgets["source"].setCurrentPath(str(path))
    else:
        _status(owner, "Choose a completed single-subject manifest / 请选择已完成的单被试运行记录")


def apply_region_language(owner, language):
    if not hasattr(owner, "_regionWidgets"):
        return
    widgets = owner._regionWidgets
    strings = TEXT["zh" if str(language).startswith("zh") else "en"]
    widgets["panel"].text = strings["title"]
    for key, label in widgets["labels"].items():
        label.text = strings[key]
    for key in ("latest", "inspect", "select", "clear", "metrics", "tracts", "graph", "run", "note"):
        widgets[key].text = strings[key]
    widgets["search"].placeholderText = strings["search"]
    for index, name in enumerate(strings["rules"]):
        widgets["rule"].setItemText(index, name)
    if not widgets["status"].text:
        widgets["status"].text = strings["empty"]


def filter_regions(owner, query):
    widgets = owner._regionWidgets
    query = str(query or "").lower().strip()
    for index in range(_count(widgets["regions"])):
        item = widgets["regions"].item(index)
        item.setHidden(query not in item.text().lower())


def set_checks(owner, checked):
    import qt

    widget = owner._regionWidgets["regions"]
    for index in range(_count(widget)):
        item = widget.item(index)
        if not checked or not item.isHidden():
            item.setCheckState(qt.Qt.Checked if checked else qt.Qt.Unchecked)


def _command(owner, args):
    script = Path(__file__).resolve().parents[1] / "scripts/analyze_regions.py"
    return [(owner._slicer_launcher_program(), ["--launch", "PythonSlicer", "-u", str(script), *args], {})]


def inspect_regions(owner):
    from shared.ui_setup_jobs import start_setup_job
    import qt
    import slicer

    widgets = owner._regionWidgets
    if getattr(owner, "_pipelineActive", False):
        _status(owner, "Wait for the current job / 请等待当前任务完成", True)
        return
    source, atlas, lut = _paths(owner)
    if not source:
        use_latest_run(owner)
        source, atlas, lut = _paths(owner)
    if not source:
        return
    catalog = Path(tempfile.mkdtemp(prefix="regions-", dir=str(slicer.app.temporaryPath))) / "catalog.json"
    args = ["--inspect", source, "--catalog", str(catalog)]
    if atlas:
        args.extend(("--atlas", atlas))
    if lut:
        args.extend(("--lut", lut))
    requested = source, atlas, lut

    def done(status, details, log_path):
        widgets["panel"].enabled = True
        if status != "completed":
            _status(owner, f"{status}: {details[-800:]}\nLog: {log_path}", True)
            return
        if requested != _paths(owner):
            invalidate_catalog(owner)
            return
        try:
            data = json.loads(catalog.read_text())
            widgets["regions"].clear()
            widgets["metric_list"].clear()
            for region in data["regions"]:
                item = qt.QListWidgetItem(f'{region["id"]}  {region["name"]}  ({region["voxels"]} voxels)')
                item.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable | qt.Qt.ItemIsUserCheckable)
                item.setData(qt.Qt.UserRole, region["id"])
                item.setCheckState(qt.Qt.Unchecked)
                widgets["regions"].addItem(item)
            for key in data["metrics"]:
                item = qt.QListWidgetItem(key)
                item.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsUserCheckable)
                item.setData(qt.Qt.UserRole, key)
                item.setCheckState(qt.Qt.Checked)
                widgets["metric_list"].addItem(item)
            for kind, combo in (("tractograms", "tract_source"), ("connectomes", "graph_source")):
                widgets[combo].clear()
                for key in data[kind]:
                    widgets[combo].addItem(key, key)
            for key, available in (
                ("metrics", bool(data["metrics"])),
                ("tracts", bool(data["tractograms"])),
                ("graph", bool(data["connectomes"])),
            ):
                widgets[key].enabled = available
                widgets[key].checked = available if key == "metrics" else False
            owner._regionCatalog = data
            widgets["run"].enabled = True
            widgets["atlas"].toolTip = data["atlas"]
            _status(
                owner,
                f'{len(data["regions"])} regions; {len(data["metrics"])} metrics; '
                f'{len(data["tractograms"])} tractograms; {len(data["connectomes"])} connectomes. '
                f'{len(data["warnings"])} unavailable/QC notices. Select regions, then analyze.',
            )
            for warning in data["warnings"]:
                owner.appendLog("[Regions] Excluded/not available: " + warning)
            filter_regions(owner, widgets["search"].text)
        except Exception as exc:
            invalidate_catalog(owner)
            _status(owner, str(exc), True)

    try:
        if start_setup_job(owner, "Inspect regional inputs / 读取脑区", _command(owner, args), done):
            widgets["panel"].enabled = False
    except Exception as exc:
        widgets["panel"].enabled = True
        _status(owner, str(exc), True)


def _checked(widget):
    import qt

    return [
        widget.item(index).data(qt.Qt.UserRole)
        for index in range(_count(widget))
        if widget.item(index).checkState() == qt.Qt.Checked
    ]


def analyze_regions(owner):
    from shared.ui_setup_jobs import start_setup_job
    from shared.region_analysis import write_json

    widgets, catalog = owner._regionWidgets, owner._regionCatalog
    if getattr(owner, "_pipelineActive", False):
        _status(owner, "Wait for the current job / 请等待当前任务完成", True)
        return
    if not catalog:
        _status(owner, "Reload regions first / 请先读取脑区", True)
        return
    selected = _checked(widgets["regions"])
    if not selected:
        _status(owner, "Select at least one region / 请至少选择一个脑区", True)
        return
    source, atlas, lut = _paths(owner)
    root = str(widgets["output"].currentPath or "").strip()
    root = Path(root) if root else Path(catalog["output_root"]) / "05_statistics/selected_regions"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_name = re.sub(r"[^A-Za-z0-9_.-]", "_", catalog["run_name"])[:80].strip(".") or "run"
    directory = root.expanduser().resolve() / run_name / stamp
    metrics = [str(key) for key in _checked(widgets["metric_list"])] if widgets["metrics"].checked else []
    request = dict(
        source_manifest=source,
        atlas_override=atlas or None,
        lut_path=lut or None,
        manifest_sha256=catalog["manifest_sha256"],
        atlas_sha256=catalog["atlas_sha256"],
        selected_labels=[int(key) for key in selected],
        metrics=metrics,
        tractogram=(
            str(widgets["tract_source"].itemData(widgets["tract_source"].currentIndex))
            if widgets["tracts"].checked
            else None
        ),
        connectome=(
            str(widgets["graph_source"].itemData(widgets["graph_source"].currentIndex))
            if widgets["graph"].checked
            else None
        ),
        tract_rule=str(widgets["rule"].itemData(widgets["rule"].currentIndex)),
        output_dir=str(directory),
    )
    if not metrics and not request["tractogram"] and not request["connectome"]:
        _status(owner, "Select an available analysis / 请启用至少一种可用分析", True)
        return
    try:
        directory.mkdir(parents=True)
        request_path = directory / "request.json"
        write_json(request_path, request)

        def done(status, details, log_path):
            widgets["panel"].enabled = True
            if status != "completed":
                _status(owner, f"{status}: {details[-800:]}\nLog: {log_path}", True)
                return
            try:
                manifest = directory / "region_analysis_manifest.json"
                record = json.loads(manifest.read_text())
                if record.get("status") != "completed":
                    raise RuntimeError("Regional job did not publish completed outputs")
                loaded = owner.logic.loadKeyResultsFromManifest(manifest, automatic=True)
                owner._latestRegionalManifestPath = manifest
                message = f'Regional analysis completed. Loaded {len(loaded["loaded"])}; warnings: {len(record["warnings"])}. '
                _status(owner, message + "Visual review pending.\n" + str(directory))
                owner.appendLog("[Regions] " + message + str(manifest))
                for warning in record["warnings"]:
                    owner.appendLog("[Regions] " + warning)
                for skipped in loaded["skipped"]:
                    owner.appendLog(
                        "[Regions] Not loaded: " + str(skipped.get("path", "")) + ": " + str(skipped.get("reason", ""))
                    )
                if loaded["skipped"]:
                    _status(
                        owner,
                        message + f'{len(loaded["skipped"])} display items unavailable; see log.\n' + str(directory),
                        True,
                    )
                owner._setStatus("warning", "Regional results loaded; review coverage and anatomy")
            except Exception as exc:
                _status(owner, str(exc), True)

        if start_setup_job(
            owner, "Selected-region analysis / 分析所选脑区", _command(owner, ["--request", str(request_path)]), done
        ):
            widgets["panel"].enabled = False
    except Exception as exc:
        widgets["panel"].enabled = True
        _status(owner, str(exc), True)
