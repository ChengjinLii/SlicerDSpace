"""Stylesheets shared by the SlicerDSpace Qt UI."""

from __future__ import annotations


SLICERDSPACE_UI_STYLE = """
QFrame#headerFrame {
  background: transparent;
  border: none;
  border-bottom: 1px solid #D8DEE3;
  border-radius: 0;
}
QLabel#headlineLabel {
  color: #24343D;
  font-size: 15px;
  font-weight: 600;
}
ctkCollapsibleButton {
  background: transparent;
  border: none;
}
QWidget#externalBackendsGroup,
ctkCollapsibleButton#externalBackendsGroup,
QGroupBox#externalBackendsGroup {
  background: #F8FAFB;
  border: 1px solid #D8DEE3;
  border-radius: 4px;
  padding: 4px;
}
QLabel#subtitleLabel, QLabel#environmentHintLabel,
QLabel#environmentResultLabel, QLabel#externalSectionDescriptionLabel,
QLabel#externalSubsectionDescriptionLabel, QLabel#advancedRunSectionLabel,
QLabel#runMessageLabel, QLabel#runStageLabel,
QLabel#advancedSettingsHintLabel {
  color: #63727D;
  background: transparent;
  border: none;
}
QLabel#logHintLabel {
  color: #334550;
  font-weight: 600;
}
QLabel#externalSectionTitleLabel, QLabel#externalSubsectionTitleLabel {
  background: transparent;
  border: none;
  color: #334550;
  font-weight: 600;
  padding: 4px 0;
}
QLabel#modelAssetsSummaryLabel, QLabel#selectedProductsSummaryLabel,
QLabel#runSummaryLabel {
  background: #F6F8FA;
  border: 1px solid #DFE5E9;
  border-radius: 4px;
  color: #52616D;
  padding: 6px;
}
QLabel#runDetailsLabel, QLabel#reviewStateLabel {
  color: #63727D;
  background: transparent;
  border: none;
  padding: 0 10px;
}
QLineEdit, QComboBox {
  background: #FFFFFF;
  border: 1px solid #CCD5DC;
  border-radius: 3px;
  padding: 2px 5px;
  min-height: 18px;
}
QLineEdit:focus, QComboBox:focus {
  border: 1px solid #476E83;
}
QPushButton {
  background: #F8FAFB;
  border: 1px solid #CCD5DC;
  border-radius: 4px;
  color: #334550;
  padding: 4px 8px;
}
QPushButton:hover:!disabled {
  background: #EEF2F5;
  border: 1px solid #9BAEBB;
}
QToolButton#microstructureAlgorithmSelectButton,
QToolButton#tractographyAlgorithmSelectButton,
QToolButton#bundlesAlgorithmSelectButton {
  color: #335B70;
  background: #FFFFFF;
  border: 1px solid #CCD5DC;
  border-radius: 3px;
  padding: 0;
  min-height: 18px;
}
QToolButton:hover { border-color: #476E83; }
QStackedWidget#advancedCategoryStack { background: transparent; border: none; }
QPushButton:disabled {
  color: #8A98A3;
  background: #F2F4F6;
}
QPushButton#runSelectedButton {
  background: #335B70;
  border: 1px solid #335B70;
  border-radius: 4px;
  color: #FFFFFF;
  font-weight: 600;
  padding: 8px 12px;
}
QPushButton#runSelectedButton:hover:!disabled {
  background: #28495C;
}
QPushButton#runSelectedButton:disabled {
  background: #E3E9ED;
  border-color: #D4DDE4;
  color: #81919C;
}
QPushButton#cancelRunButton {
  background: #FFFFFF;
  color: #A7403E;
  border: 1px solid #D8BAB9;
  padding: 8px;
}
QPushButton#clearLogButton {
  background: transparent;
  border: none;
  color: #63727D;
  padding: 3px 6px;
}
QProgressBar {
  background: #E8EDF1;
  border: none;
  border-radius: 3px;
  color: #334550;
  max-height: 16px;
  text-align: center;
}
QProgressBar::chunk {
  background: #9EB8C8;
  border-radius: 3px;
}
QPlainTextEdit#logPlainTextEdit {
  background: #F7F9FB;
  border: 1px solid #D8DEE3;
  border-radius: 4px;
  color: #425360;
  font-family: "DejaVu Sans Mono", "Consolas", monospace;
  font-size: 11px;
  selection-background-color: #D4E2EA;
  selection-color: #223642;
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
    "completed": ("#F0FAF3", "#174D32"),
    "passed": ("#F0FAF3", "#174D32"),
    "skipped": ("#F3F7F4", "#2F4038"),
    "planned": ("#EEF6FF", "#163E50"),
    "running": ("#EEF6FF", "#163E50"),
    "partial": ("#FFF8EA", "#6B3F00"),
    "blocked": ("#FFF3E8", "#6B3F00"),
    "failed": ("#FDECEC", "#6B1A1A"),
    "cancelled": ("#FFF3E8", "#6B3F00"),
    "unknown": ("#F3F7F4", "#2F4038"),
}


def run_summary_label_style(state: str) -> str:
    """Return the stylesheet for the run-summary label state."""

    background, text = RUN_SUMMARY_PALETTE.get(state, RUN_SUMMARY_PALETTE["unknown"])
    return (
        "QLabel#runSummaryLabel { "
        f"background-color: {background}; border: 1px solid #D8E4DD; "
        f"border-radius: 7px; color: {text}; "
        "padding: 7px 9px; font-size: 11px; }"
    )
