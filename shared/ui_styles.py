"""Stylesheets shared by the SlicerDDSurfer Qt UI."""

from __future__ import annotations


SLICERDDSURFER_UI_STYLE = """
QFrame#headerFrame {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F2F8F4, stop:1 #E9F2F5);
  border: 1px solid #CBD8D2;
  border-radius: 10px;
  padding: 14px;
}
QLabel#headlineLabel {
  color: #163526;
  font-size: 21px;
  font-weight: 700;
}
QWidget#externalBackendsGroup,
ctkCollapsibleButton#externalBackendsGroup,
QGroupBox#externalBackendsGroup {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCFEFC, stop:1 #F4F8F5);
  border: 1px solid #CADBD0;
  border-radius: 14px;
  padding: 8px;
}
QLabel#subtitleLabel,
QLabel#environmentHintLabel,
QLabel#logHintLabel {
  color: #536B61;
  font-size: 12px;
}
QLabel#externalSectionTitleLabel {
  background: #EAF3ED;
  border: 1px solid #CFE1D5;
  border-radius: 8px;
  color: #183F2E;
  font-size: 14px;
  font-weight: 700;
  padding: 8px 10px;
}
QLabel#externalSectionDescriptionLabel {
  color: #5C7168;
  font-size: 11px;
  padding: 2px 8px 8px 10px;
}
QLabel#externalSubsectionTitleLabel {
  background: #F4F8F5;
  border: 1px solid #DDEAE2;
  border-radius: 7px;
  color: #315843;
  font-size: 12px;
  font-weight: 700;
  padding: 7px 9px;
}
QLabel#externalSubsectionDescriptionLabel {
  color: #6A7D74;
  font-size: 11px;
  padding: 1px 8px 5px 9px;
}
QLabel#configurationSectionLabel,
QLabel#targetsSectionLabel,
QLabel#runStepSectionLabel {
  background: #ECF5EF;
  border: 1px solid #CFE1D5;
  border-left: 5px solid #1D6C45;
  border-radius: 9px;
  color: #173126;
  font-size: 14px;
  font-weight: 800;
  padding: 9px 11px;
}
ctkCollapsibleButton#advancedRunCollapsibleButton,
QGroupBox#advancedRunCollapsibleButton {
  background: #FBFDFB;
  border: 1px solid #D7E4DC;
  border-radius: 12px;
  padding: 7px;
}
QLabel#modelAssetsSummaryLabel {
  background-color: #F6FAF7;
  border: 1px solid #D6E3DA;
  border-radius: 8px;
  color: #294B3B;
  padding: 8px 10px;
  font-size: 11px;
}
QLabel#advancedRunSectionLabel {
  background: #F7FAF8;
  border: 1px solid #DFE9E2;
  border-radius: 8px;
  color: #42584D;
  font-size: 12px;
  padding: 8px 10px;
}
QLabel#batchModeLabel,
QLabel#batchRootLabel,
QLabel#batchSizeLabel,
QLabel#batchArrangeInputsLabel {
  color: #244D3A;
  font-weight: 700;
  padding: 5px 0;
}
QCheckBox#batchModeCheckBox,
QSpinBox#batchSizeSpinBox,
QComboBox#batchArrangeInputsComboBox,
ctkPathLineEdit#batchRootPath {
  background: #FBFEFC;
  border: 1px solid #CFE0D5;
  border-radius: 8px;
  padding: 6px 8px;
  min-height: 24px;
}
QCheckBox#batchModeCheckBox {
  color: #243A31;
  font-weight: 600;
}
QCheckBox#batchModeCheckBox:hover,
QSpinBox#batchSizeSpinBox:hover,
QComboBox#batchArrangeInputsComboBox:hover,
ctkPathLineEdit#batchRootPath:hover {
  border: 1px solid #9EC6AD;
  background: #F6FBF8;
}
QWidget#externalBackendsGroup QLineEdit {
  background: white;
  border: 1px solid #CBD8D0;
  border-radius: 8px;
  padding: 7px 10px;
  min-height: 20px;
}
QWidget#externalBackendsGroup QLineEdit:focus {
  border: 1px solid #2D7C92;
  background: #FCFEFD;
}
QWidget#externalBackendsGroup QPushButton {
  border: 1px solid #CFDCD4;
  border-radius: 8px;
  padding: 6px 12px;
  background: #FFFFFF;
  color: #31503F;
}
QWidget#externalBackendsGroup QPushButton:hover:!disabled {
  background: #F0F6F2;
  border: 1px solid #BCD3C4;
}
QLabel#selectedProductsSummaryLabel {
  background-color: #F8FBF8;
  border: 1px solid #D6E3DA;
  border-left: 4px solid #1D6C45;
  border-radius: 7px;
  color: #294B3B;
  padding: 8px 10px;
  font-family: "Menlo", "Consolas", monospace;
  font-size: 11px;
}
QLabel#runSummaryLabel {
  background-color: #F7FAF8;
  border: 1px solid #D8E4DD;
  border-left: 4px solid #6B7E73;
  border-radius: 7px;
  color: #2F4038;
  padding: 7px 9px;
  font-size: 11px;
}
QPushButton#runSelectedButton {
  background-color: #1D6C45;
  border: 1px solid #155336;
  border-radius: 7px;
  color: white;
  font-weight: 700;
  padding: 8px 16px;
}
QPushButton#runSelectedButton:hover:!disabled {
  background-color: #155336;
}
QPushButton#validateButton {
  background-color: transparent;
  border: 1px solid #2D7C92;
  border-radius: 7px;
  color: #2D7C92;
  font-weight: 600;
  padding: 6px 12px;
}
QPushButton#validateButton:hover:!disabled {
  background-color: rgba(45, 124, 146, 0.10);
}
QPushButton#clearLogButton {
  background-color: transparent;
  border: 1px solid #B8C6C0;
  border-radius: 6px;
  color: #43594F;
  padding: 4px 9px;
}
QPushButton#clearLogButton:hover:!disabled {
  background-color: rgba(184, 198, 192, 0.28);
}
QPlainTextEdit#logPlainTextEdit {
  background-color: #132018;
  border: 1px solid #2E4B39;
  border-radius: 8px;
  color: #E5F0DF;
  font-family: "Menlo", "Consolas", monospace;
  font-size: 11px;
  selection-background-color: #2D7C92;
}
"""

RUN_STATUS_TABLE_STYLE = (
    "QTableWidget { background: #FBFCFA; alternate-background-color: #F2F6F3; "
    "gridline-color: #D7E0DA; selection-background-color: #DCEBE2; selection-color: #163526; } "
    "QHeaderView::section { background: #E6EFE9; color: #294B3B; font-weight: 700; padding: 5px; border: 0; }"
)

ENVIRONMENT_RESULTS_DIALOG_STYLE = """
QDialog {
  background: #F4F7F6;
}
QLabel#environmentSummaryLabel {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EEF6F1, stop:1 #F7FBF9);
  color: #173126;
  padding: 14px 16px;
  border: 1px solid #CADCD1;
  border-radius: 10px;
  font-weight: 600;
}
QFrame#environmentItemFrame {
  border: 1px solid #D5DEDC;
  border-radius: 10px;
  background: #FFFFFF;
}
QLabel#environmentItemText {
  color: #223238;
  background: transparent;
}
QPushButton {
  min-height: 30px;
  padding: 6px 14px;
  border: 1px solid #C8D4D1;
  border-radius: 8px;
  background: #FFFFFF;
  color: #173126;
}
QPushButton:hover {
  background: #F1F6F4;
}
QPushButton:pressed {
  background: #E3EEE8;
}
QPlainTextEdit {
  background: #FFFFFF;
  color: #4A5C5F;
  border: 1px solid #D7E0DE;
  border-radius: 8px;
  padding: 6px;
}
QScrollArea {
  border: none;
  background: transparent;
}
"""

ENVIRONMENT_READY_LABEL_STYLE = "QLabel { color: #2E7D32; padding: 12px; }"

RUN_SUMMARY_PALETTE = {
    "completed": ("#F0FAF3", "#1D6C45", "#174D32"),
    "passed": ("#F0FAF3", "#1D6C45", "#174D32"),
    "skipped": ("#F3F7F4", "#6B7E73", "#2F4038"),
    "planned": ("#EEF6FF", "#2D7C92", "#163E50"),
    "running": ("#EEF6FF", "#2D7C92", "#163E50"),
    "partial": ("#FFF8EA", "#E28A11", "#6B3F00"),
    "blocked": ("#FFF3E8", "#EF6C00", "#6B3F00"),
    "failed": ("#FDECEC", "#C62828", "#6B1A1A"),
    "cancelled": ("#FFF3E8", "#EF6C00", "#6B3F00"),
    "unknown": ("#F3F7F4", "#6B7E73", "#2F4038"),
}


def run_summary_label_style(state: str) -> str:
    """Return the stylesheet for the run-summary label state."""

    background, accent, text = RUN_SUMMARY_PALETTE.get(state, RUN_SUMMARY_PALETTE["unknown"])
    return (
        "QLabel#runSummaryLabel { "
        f"background-color: {background}; border: 1px solid #D8E4DD; "
        f"border-left: 4px solid {accent}; border-radius: 7px; color: {text}; "
        "padding: 7px 9px; font-size: 11px; }"
    )
