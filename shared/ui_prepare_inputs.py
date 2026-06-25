"""Qt builders for preparing external DWI inputs from the Slicer UI."""

from __future__ import annotations

from typing import Any


def install_prepare_inputs_panel(owner: Any, configuration_layout: Any) -> None:
    """Install a compact Prepare Inputs panel into the main workflow section."""

    import qt

    owner._prepareInputWidgets = {}

    try:
        import ctk

        panel = ctk.ctkCollapsibleButton()
        panel.text = "Prepare Inputs"
        panel.collapsed = True
    except Exception:
        panel = qt.QGroupBox("Prepare Inputs")
    panel.setObjectName("prepareInputsPanel")
    panel.setToolTip("Normalize DICOM, NRRD/NHDR, or NIfTI+bval/bvec inputs into a SlicerDDSurfer subject root.")
    panel.setStyleSheet(
        "QWidget#prepareInputsPanel { background: #F7FAF8; border: 1px solid #D6E4DC; border-radius: 8px; }"
    )

    form_layout = qt.QFormLayout(panel)
    form_layout.setSpacing(8)
    form_layout.setContentsMargins(10, 10, 10, 10)

    summary = qt.QLabel(
        "Use this when inputs are not already organized as input/data.nii.gz, input/bvals and input/bvecs. "
        "The import writes input/input_import_manifest.json and the workflow continues from the canonical subject root."
    )
    summary.wordWrap = True
    summary.setStyleSheet(
        "QLabel { background: #EEF6F1; border: 1px solid #CFE1D5; border-radius: 6px; color: #274737; padding: 7px; }"
    )
    form_layout.addRow(summary)

    source_kind = qt.QComboBox()
    for label in ("auto", "dicom", "nifti", "nrrd", "canonical"):
        source_kind.addItem(label)
    source_kind.setToolTip("Use auto unless you need to force a specific source type.")
    owner._prepareInputWidgets["source_kind"] = source_kind
    form_layout.addRow("Source type", source_kind)

    source_row, source_edit = _path_row(
        owner,
        key="source",
        placeholder="DICOM folder, DWI NIfTI, NRRD/NHDR, or canonical subject root",
        browse_callback=owner._browse_prepare_input_source_path,
    )
    form_layout.addRow("Source", source_row)
    owner._prepareInputWidgets["source"] = source_edit

    subject_root_row, subject_root_edit = _path_row(
        owner,
        key="subject_root",
        placeholder="Destination subject root, e.g. /data/study/sub-01",
        browse_callback=owner._browse_prepare_input_subject_root,
    )
    form_layout.addRow("Subject root", subject_root_row)
    owner._prepareInputWidgets["subject_root"] = subject_root_edit

    subject_id = qt.QLineEdit()
    subject_id.setPlaceholderText("sub-01")
    subject_id.setToolTip("Subject identifier recorded in input/input_import_manifest.json.")
    owner._prepareInputWidgets["subject_id"] = subject_id
    form_layout.addRow("Subject ID", subject_id)

    sidecar_summary = qt.QLabel("Optional sidecars for NIfTI inputs or externally generated masks.")
    sidecar_summary.setStyleSheet("QLabel { color: #5B7167; padding-top: 4px; }")
    form_layout.addRow(sidecar_summary)

    for key, label, placeholder in (
        ("bval", "bval", "Optional .bval sidecar"),
        ("bvec", "bvec", "Optional .bvec sidecar"),
        ("metadata", "Metadata JSON", "Optional BIDS-style .json sidecar"),
        ("mask", "Brain mask", "Optional nodif_brain_mask.nii.gz"),
    ):
        row, edit = _path_row(owner, key=key, placeholder=placeholder, browse_callback=owner._browse_prepare_input_file)
        form_layout.addRow(label, row)
        owner._prepareInputWidgets[key] = edit

    backend = qt.QComboBox()
    for label in ("auto", "copy", "dcm2niix", "mrconvert", "dwiconvert"):
        backend.addItem(label)
    backend.setToolTip("Use auto unless you need to force dcm2niix, MRtrix3 mrconvert, SlicerDMRI DWIConvert, or copy.")
    owner._prepareInputWidgets["backend"] = backend
    form_layout.addRow("Backend", backend)

    output_kind = qt.QComboBox()
    for label in ("canonical-nifti", "compat-nrrd"):
        output_kind.addItem(label)
    output_kind.setToolTip("canonical-nifti is preferred. compat-nrrd is available for legacy DWIConvert routes.")
    owner._prepareInputWidgets["output_kind"] = output_kind
    form_layout.addRow("Output", output_kind)

    options_row = qt.QWidget()
    options_layout = qt.QHBoxLayout(options_row)
    options_layout.setContentsMargins(0, 0, 0, 0)
    dry_run = qt.QCheckBox("Dry run")
    dry_run.setToolTip("Plan the import without writing files.")
    force = qt.QCheckBox("Overwrite existing files")
    force.setToolTip("Allow replacing existing files in the destination input folder.")
    owner._prepareInputWidgets["dry_run"] = dry_run
    owner._prepareInputWidgets["force"] = force
    options_layout.addWidget(dry_run)
    options_layout.addWidget(force)
    options_layout.addStretch(1)
    form_layout.addRow("Options", options_row)

    buttons = qt.QHBoxLayout()
    preview_button = qt.QPushButton("Preview plan")
    preview_button.setToolTip("Build and show the input import plan without writing files.")
    preview_button.connect("clicked()", owner._on_prepare_inputs_preview_clicked)
    prepare_button = qt.QPushButton("Prepare inputs")
    prepare_button.setToolTip("Create the canonical subject-root input folder and write input_import_manifest.json.")
    prepare_button.connect("clicked()", owner._on_prepare_inputs_clicked)
    manifest_button = qt.QPushButton("Open manifest")
    manifest_button.setToolTip("Open input/input_import_manifest.json for the selected subject root.")
    manifest_button.connect("clicked()", owner._on_open_prepare_input_manifest_clicked)
    owner._prepareInputWidgets["preview_button"] = preview_button
    owner._prepareInputWidgets["prepare_button"] = prepare_button
    owner._prepareInputWidgets["manifest_button"] = manifest_button
    buttons.addWidget(preview_button)
    buttons.addWidget(prepare_button)
    buttons.addWidget(manifest_button)
    buttons.addStretch(1)
    form_layout.addRow("Actions", buttons)

    try:
        configuration_layout.insertWidget(2, panel)
    except Exception:
        configuration_layout.addWidget(panel)


def _path_row(owner: Any, *, key: str, placeholder: str, browse_callback):
    import qt

    row = qt.QWidget()
    row_layout = qt.QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    edit = qt.QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setToolTip(placeholder)
    row_layout.addWidget(edit, 1)
    browse = qt.QPushButton("Browse...")
    browse.setToolTip(placeholder)
    browse.connect("clicked()", lambda key=key: browse_callback(key))
    row_layout.addWidget(browse)
    clear = qt.QPushButton("Clear")
    clear.connect("clicked()", lambda edit=edit: edit.setText(""))
    row_layout.addWidget(clear)
    return row, edit
