"""Qt builders for the SlicerDDSurfer environment-path settings panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.dependency_config import UI_DEPENDENCY_PATHS
from shared.ui_environment_panel import environment_path_entries, dependency_backend_group, model_assets_summary_text


def install_environment_dependency_path_controls(owner: Any, environment_layout: Any) -> None:
    """Install the schema-driven environment dependency path controls."""

    import qt

    owner._environmentPathLineEdits = {}
    owner._environmentPathStatusLabels = {}
    owner._environmentBackendSectionLabels = {}
    owner._environmentBackendSectionRows = {"wma": [], "tractcloud": []}

    python_target_label = qt.QLabel(owner._python_install_target_text())
    python_target_label.setObjectName("environmentPythonTargetLabel")
    python_target_label.wordWrap = True
    python_target_label.setStyleSheet(
        "QLabel { background: #F5F7F9; color: #455A64; padding: 6px; border-radius: 4px; }"
    )
    python_target_label.visible = False
    owner._environmentPythonTargetLabel = python_target_label

    group_box, form_layout = _build_environment_group()
    owner._environmentAdvancedPathsWidget = group_box

    for entry in environment_path_entries(UI_DEPENDENCY_PATHS):
        if entry.kind == "section":
            add_environment_section_header(form_layout, entry.title, entry.description)
        elif entry.kind == "subsection":
            owner._environmentBackendSectionLabels[entry.subsection] = add_environment_subsection_label(
                form_layout,
                entry.title,
                entry.description,
            )
        elif entry.kind == "row" and entry.item:
            add_environment_path_row(owner, form_layout, entry.item)
        elif entry.kind == "model-assets":
            add_model_assets_row(owner, form_layout)

    add_dependency_config_buttons(owner, form_layout)

    try:
        insert_index = max(0, environment_layout.count() - 1)
        environment_layout.insertWidget(insert_index, python_target_label)
        insert_index += 1
        environment_layout.insertWidget(insert_index, group_box)
    except Exception:
        environment_layout.addWidget(python_target_label)
        environment_layout.addWidget(group_box)


def _build_environment_group():
    import qt

    tooltip = (
        "Discovery order: saved path, environment variables, PATH, then common install paths. "
        "Leave fields empty to rely on automatic discovery."
    )
    try:
        import ctk

        group_box = ctk.ctkCollapsibleButton()
        group_box.setObjectName("externalBackendsGroup")
        group_box.text = "External Runtime Paths"
        group_box.collapsed = True
        group_box.setToolTip(tooltip)
        form_layout = qt.QFormLayout(group_box)
    except Exception:
        group_box = qt.QGroupBox("External Runtime Paths")
        group_box.setObjectName("externalBackendsGroup")
        group_box.setToolTip(tooltip)
        form_layout = qt.QFormLayout(group_box)

    form_layout.setSpacing(8)
    form_layout.setContentsMargins(10, 10, 10, 10)
    group_box.setToolTip(tooltip)
    return group_box, form_layout


def add_dependency_config_buttons(owner: Any, form_layout: Any) -> None:
    import qt

    config_buttons = qt.QHBoxLayout()
    import_button = qt.QPushButton("Import dependency config")
    import_button.setToolTip("Load a SlicerDDSurfer dependency config JSON and save the external paths into Slicer settings.")
    import_button.connect("clicked()", owner._on_import_dependency_config_clicked)
    export_button = qt.QPushButton("Export dependency config")
    export_button.setToolTip("Save the currently configured external paths as a CLI-compatible JSON config.")
    export_button.connect("clicked()", owner._on_export_dependency_config_clicked)
    owner._environmentImportConfigButton = import_button
    owner._environmentExportConfigButton = export_button
    config_buttons.addWidget(import_button)
    config_buttons.addWidget(export_button)

    report_button = qt.QPushButton("Open environment report")
    report_button.setToolTip("Open the latest environment_doctor.json directory after a dependency check.")
    report_button.connect("clicked()", owner._on_open_environment_report_dir_clicked)
    config_buttons.addWidget(report_button)

    install_logs_button = qt.QPushButton("Open install logs")
    install_logs_button.setToolTip("Open the latest Python dependency install logs/results directory.")
    install_logs_button.connect("clicked()", owner._on_open_install_logs_dir_clicked)
    config_buttons.addWidget(install_logs_button)

    config_buttons.addStretch(1)
    form_layout.addRow("Config", config_buttons)


def add_environment_path_row(owner: Any, form_layout: Any, item: dict[str, str]) -> None:
    import qt

    dependency_id = item["id"]
    row = qt.QWidget()
    row_layout = qt.QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)

    line_edit = qt.QLineEdit()
    line_edit.setText(owner._read_environment_path_setting(dependency_id))
    line_edit.setPlaceholderText("Auto-detect if empty")
    line_edit.setToolTip(item["tooltip"])
    line_edit.editingFinished.connect(
        lambda dependency_id=dependency_id, line_edit=line_edit: owner._on_environment_dependency_path_edited(
            dependency_id,
            line_edit,
        )
    )
    row_layout.addWidget(line_edit, 1)

    browse_button = qt.QPushButton("Browse...")
    browse_button.setToolTip(item["tooltip"])
    browse_button.connect(
        "clicked()",
        lambda item=item, line_edit=line_edit: owner._browse_environment_dependency_path(item, line_edit),
    )
    row_layout.addWidget(browse_button)

    clear_button = qt.QPushButton("Clear")
    clear_button.connect(
        "clicked()",
        lambda dependency_id=dependency_id, line_edit=line_edit: owner._clear_environment_dependency_path(
            dependency_id,
            line_edit,
        ),
    )
    row_layout.addWidget(clear_button)

    status_label = qt.QLabel("not checked")
    status_label.setMinimumWidth(130)
    status_label.setStyleSheet("QLabel { color: #78909C; }")
    row_layout.addWidget(status_label)

    form_layout.addRow(item["label"], row)
    owner._environmentPathLineEdits[dependency_id] = line_edit
    owner._environmentPathStatusLabels[dependency_id] = status_label
    backend_group = dependency_backend_group(dependency_id)
    if backend_group:
        owner._environmentBackendSectionRows[backend_group].append(
            (line_edit, browse_button, clear_button, status_label)
        )


def add_environment_section_header(form_layout: Any, title: str, description: str) -> None:
    import qt

    title_label = qt.QLabel(title)
    title_label.setObjectName("externalSectionTitleLabel")
    title_label.setStyleSheet(
        "QLabel { background: #EAF3ED; border: 1px solid #CFE1D5; border-radius: 8px; "
        "color: #183F2E; font-weight: 700; padding: 8px 10px; }"
    )
    description_label = qt.QLabel(description)
    description_label.setObjectName("externalSectionDescriptionLabel")
    description_label.wordWrap = True
    description_label.setStyleSheet("QLabel { color: #5C7168; padding: 2px 8px 8px 10px; }")
    form_layout.addRow(title_label)
    form_layout.addRow("", description_label)


def add_environment_subsection_label(form_layout: Any, title: str, description: str):
    import qt

    title_label = qt.QLabel(title)
    title_label.setObjectName("externalSubsectionTitleLabel")
    title_label.setStyleSheet(
        "QLabel { background: #F4F8F5; border: 1px solid #DDEAE2; border-radius: 7px; "
        "color: #315843; font-weight: 700; padding: 7px 9px; }"
    )
    description_label = qt.QLabel(description)
    description_label.setObjectName("externalSubsectionDescriptionLabel")
    description_label.wordWrap = True
    description_label.setStyleSheet("QLabel { color: #6A7D74; padding: 1px 8px 5px 9px; }")
    form_layout.addRow(title_label)
    form_layout.addRow("", description_label)
    return (title_label, description_label)


def add_model_assets_row(owner: Any, form_layout: Any) -> None:
    import qt

    row = qt.QWidget()
    row_layout = qt.QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)

    summary = qt.QLabel(model_assets_summary_text(Path(__file__).resolve().parent.parent))
    summary.setObjectName("modelAssetsSummaryLabel")
    summary.wordWrap = True
    summary.setStyleSheet(
        "QLabel { background: #F7FAF8; border: 1px solid #D8E4DD; border-radius: 6px; color: #355244; padding: 6px; }"
    )
    row_layout.addWidget(summary, 1)
    owner._modelAssetsSummaryLabel = summary

    status_button = qt.QPushButton("Check status")
    status_button.setToolTip("Check whether core and all model asset profiles are present and not Git LFS pointer files.")
    status_button.connect("clicked()", owner._on_check_model_assets_status_clicked)
    row_layout.addWidget(status_button)
    owner._modelAssetsCheckStatusButton = status_button

    verify_button = qt.QPushButton("Verify core")
    verify_button.setToolTip("Verify the core model asset profile required by DDSurfer, DDSeg, and DDParcel.")
    verify_button.connect("clicked()", owner._on_verify_core_model_assets_clicked)
    row_layout.addWidget(verify_button)
    owner._modelAssetsVerifyCoreButton = verify_button

    lockfile_button = qt.QPushButton("Write lockfile")
    lockfile_button.setToolTip("Write a SHA256 lockfile for the core model asset profile.")
    lockfile_button.connect("clicked()", owner._on_write_model_asset_lockfile_clicked)
    row_layout.addWidget(lockfile_button)
    owner._modelAssetsWriteLockfileButton = lockfile_button

    guide_button = qt.QPushButton("Open guide")
    guide_button.setToolTip("Open docs/assets/MODEL_ASSETS.md for unified model weights/template download and verification.")
    guide_button.connect("clicked()", owner._on_open_model_assets_guide_clicked)
    row_layout.addWidget(guide_button)

    terms_button = qt.QPushButton("Terms")
    terms_button.setToolTip("Open docs/assets/MODEL_ASSET_TERMS.md.")
    terms_button.connect("clicked()", owner._on_open_model_asset_terms_clicked)
    row_layout.addWidget(terms_button)

    manifest_button = qt.QPushButton("Open manifest")
    manifest_button.setToolTip("Open models/assets_manifest.json.")
    manifest_button.connect("clicked()", owner._on_open_model_assets_manifest_clicked)
    row_layout.addWidget(manifest_button)

    provenance_button = qt.QPushButton("Provenance")
    provenance_button.setToolTip("Show model asset profile, verification, lockfile, and release-boundary notes.")
    provenance_button.connect("clicked()", owner._on_show_model_asset_provenance_clicked)
    row_layout.addWidget(provenance_button)

    release_button = qt.QPushButton("Release notes")
    release_button.setToolTip("Open docs/release/RELEASE_NOTES_v0.1.0.md.")
    release_button.connect("clicked()", owner._on_open_release_notes_clicked)
    row_layout.addWidget(release_button)

    form_layout.addRow("Model assets bundle", row)
