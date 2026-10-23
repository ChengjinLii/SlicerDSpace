"""Three matching multi-select buttons beside the product checkboxes."""

from shared.algorithm_selection import TRACKING, BUNDLES, LABELS, algorithms

FAMILIES = {
    "microstructure": ("targetMicrostructureCheckBox", ("dti", "freewater", "noddi", "dki"), "orchestrationMicrostructureStages"),
    "tractography": ("targetTractographyCheckBox", TRACKING, "orchestrationTractographyBackend"),
    "bundles": ("targetBundlesCheckBox", BUNDLES, "orchestrationBundleBackend"),
}


def selected_algorithms(node, family):
    _, choices, attribute = FAMILIES[family]
    return algorithms(getattr(node, attribute, ""), choices, choices[0])


def set_algorithms(owner, family, values):
    _, choices, attribute = FAMILIES[family]
    selected = algorithms(",".join(values), choices, choices[0]) if values else ()
    if not selected:
        raise ValueError("Select at least one algorithm")
    import slicer
    if family == "microstructure" and "dti" not in selected:
        selected = ("dti", *selected)
    selected = tuple(value for value in choices if value in selected)
    with slicer.util.NodeModify(owner._parameterNode):
        setattr(owner._parameterNode, attribute, ",".join(selected))
        if family == "microstructure":
            for stage, field in (("freewater", "orchestrationRunFreeWater"), ("noddi", "orchestrationRunNoddi"), ("dki", "orchestrationRunDki")):
                setattr(owner._parameterNode, field, stage in selected)
    owner._lastEnvironmentResult = owner._lastEnvironmentSignature = None
    owner._refresh_advanced_run_settings()
    owner._schedule_common_user_settings_save()


def choose_algorithms(owner, family):
    import qt
    import slicer
    if getattr(owner, "_pipelineActive", False) or getattr(owner, "_selectedSetupActive", False):
        return False
    zh = getattr(owner, "_onboardingLanguage", "en").startswith("zh")
    _, choices, _ = FAMILIES[family]
    dialog = qt.QDialog(slicer.util.mainWindow())
    dialog.objectName = "algorithmPicker_" + family
    dialog.windowTitle = ("选择算法（可多选）" if zh else "Select algorithms (multiple allowed)")
    layout = qt.QVBoxLayout(dialog)
    hint = qt.QLabel("勾选本次需要的算法。" if zh else "Choose the algorithms to run.")
    hint.wordWrap = True
    layout.addWidget(hint)
    boxes = {}
    current = selected_algorithms(owner._parameterNode, family)
    for value in choices:
        box = qt.QCheckBox(LABELS[value])
        box.objectName = "algorithm_" + value
        box.checked = value in current
        if family == "microstructure" and value == "dti":
            box.checked = True
            box.enabled = False
            box.text += "（基础步骤）" if zh else " (required preparation)"
        boxes[value] = box
        layout.addWidget(box)
    note = qt.QLabel(("多种追踪方法将顺序运行，结果分别保存；束分析和连接组按各追踪结果分别计算，不混合流线。" if zh else
                     "Tracking methods run sequentially with separate outputs. Selected bundles/connectomes are computed per tracking method; streamlines are not mixed.")
                    if family == "tractography" else
                    ("可在高级设置调整参数；不改变各算法的数据条件或 QC 门槛。" if zh else
                     "Adjust parameters in Advanced settings. Acquisition requirements and QC gates are unchanged."))
    note.wordWrap = True
    note.setMaximumWidth(380)
    layout.addWidget(note)
    buttons = qt.QDialogButtonBox(dialog)
    buttons.setStandardButtons(qt.QDialogButtonBox.Apply | qt.QDialogButtonBox.Cancel)
    apply = buttons.button(qt.QDialogButtonBox.Apply)
    apply.text = "应用" if zh else "Apply"
    def update(*_):
        apply.enabled = any(box.checked for box in boxes.values())
    for box in boxes.values():
        box.toggled.connect(update)
    update()
    apply.connect("clicked()", dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    accepted = dialog.exec_() == qt.QDialog.Accepted
    if accepted:
        set_algorithms(owner, family, [value for value, box in boxes.items() if box.checked])
    dialog.deleteLater()
    return accepted


def fit_summary_height(label):
    """Minimum height = the height of the wrapped text at the label's width (0 when not laid out)."""
    need = label.heightForWidth(label.width) if label.width > 0 else -1
    if need > 0 and label.minimumHeight != need:
        label.setMinimumHeight(need)


def _summary_height_filter():
    import qt

    class SummaryHeightFilter(qt.QObject):
        def eventFilter(self, obj, event):
            if event.type() == qt.QEvent.Resize:
                fit_summary_height(obj)
            return False
    return SummaryHeightFilter()


def install_algorithm_pickers(owner):
    import qt
    owner._algorithmButtons = {}
    owner._algorithmSummaryLabels = {}
    owner._summaryHeightFilter = _summary_height_filter()
    form = owner.ui.targetProductsFormLayout
    form.setVerticalSpacing(4)
    for row, (family, (name, _, _)) in enumerate(FAMILIES.items(), start=5):
        checkbox = getattr(owner.ui, name)
        role = qt.QFormLayout.FieldRole
        form.takeAt(form.indexOf(checkbox))
        container = qt.QWidget()
        layout = qt.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        checkbox.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
        # Keep the checkbox's full accessible text, but render the summary in a
        # wrapping label so multi-selection never forces a wider Slicer dock.
        checkbox.setFixedWidth(20)
        layout.addWidget(checkbox, 0, qt.Qt.AlignTop)
        summary = qt.QLabel()
        summary.wordWrap = True
        # The collapsible sections above do not pass height-for-width on, so a wrapped summary
        # kept a one-line row and its second line was clipped (narrow docks). Give the label the
        # height its text needs at its current width whenever it is resized.
        policy = qt.QSizePolicy(qt.QSizePolicy.Ignored, qt.QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        summary.setSizePolicy(policy)
        summary.setMinimumWidth(0)
        summary.installEventFilter(owner._summaryHeightFilter)
        layout.addWidget(summary, 1)
        owner._algorithmSummaryLabels[name] = summary
        button = qt.QToolButton()
        button.objectName = family + "AlgorithmSelectButton"
        button.setFixedSize(28, 22)
        button.clicked.connect(lambda _checked=False, family=family: choose_algorithms(owner, family))
        layout.addWidget(button, 0, qt.Qt.AlignTop)
        form.setWidget(row, role, container)
        owner._algorithmButtons[family] = button
    refresh_picker_language(owner)


def refresh_picker_language(owner):
    zh = getattr(owner, "_onboardingLanguage", "en").startswith("zh")
    for family, button in getattr(owner, "_algorithmButtons", {}).items():
        selected = selected_algorithms(getattr(owner, "_parameterNode", None), family)
        name = {"microstructure": ("微结构分析", "microstructure"),
                "tractography": ("纤维追踪", "tractography"),
                "bundles": ("纤维束分析", "bundle analysis")}[family][0 if zh else 1]
        action = "选择" + name + "算法" if zh else "Select " + name + " algorithms"
        button.text = "..."
        button.setAccessibleName(action)
        button.toolTip = action + ("（可多选）。当前：" if zh else " (multiple allowed). Current: ") + ", ".join(LABELS[value] for value in selected)
