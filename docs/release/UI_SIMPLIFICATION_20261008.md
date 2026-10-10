# Compact Slicer UI validation (2026-10-08)

## Interface

The default module screen contains the subject inputs, product checkboxes,
one Run button, a concise status line and a bounded live log. Language selection
is in the header. The Beginner section and automatic first-run wizard are no
longer shown. A cancelled/running job still has a Cancel button while active.

Advanced settings starts collapsed and contains four groups:

- Input import / conversion: DICOM, NRRD/NHDR and NIfTI plus gradient sidecars
  can still be converted into the canonical subject directory. This tool no
  longer occupies a row in the main Inputs section.
- Analysis parameters: preprocessing/tracking/bundle backends, microstructure
  stages, topup parameters, streamline count, batch and connectome options.
- Environment and models: dependency paths, installation and model verification.
- Results and QC: run history, scene loading/replacement/clearing and reports.

Existing widgets are moved, not duplicated. Their parameter-node and callback
bindings remain intact. Diagnostic/configuration buttons are available in
Advanced. Demo and wizard handlers remain callable for compatibility/testing,
but their Beginner UI is hidden. No scientific algorithms or default numerical
parameters were changed by this UI work.

The stylesheet is scoped to the module, with neutral gray surfaces and one
blue-gray Run accent. There are no gradients or decorative colored sidebars.
Untouched empty inputs are neutral; input validation and Run gating remain in
place. Waiting-field messages now follow the selected language. Font/DPI scaling
for the rest of Slicer is not overridden.

## Verification

- Python discovery: **698 tests; 696 passed, 2 Windows PowerShell tests skipped**.
  Evidence: `ignore/validation/ui_compact_20261008/unit_tests_final.log`.
- Real Slicer 5.10 GUI: **8/8 passed**: compact layout, environment button,
  GUI/scene operations, dependency workflow, Demo workflow, run planning,
  background cancellation and output-tree loading.
  Evidence: `ignore/validation/ui_compact_20261008/final/gui_acceptance.json`.
- Compact-layout checks cover English/Chinese at 440/540 px, all three Advanced
  groups at 440 px, parameter bindings, language persistence, log clearing and
  active-only cancellation. Screenshots and details are under
  `ignore/validation/ui_compact_20261008/final/compact_ui/`.
- An expand/collapse regression was found and fixed: the outer Slicer layout
  previously retained the expanded height. The restored main view is 686 px
  high in the tested configuration, rather than 1090 px.

The subsequent import-relocation/window-size pass was independently checked:

- **84 UI unit tests passed** after the follow-up changes.
- **2/2 real Slicer GUI tests passed**: compact UI and input preparation.
  Evidence: `ignore/validation/ui_compact_20261008/small_window_verified/`.
  The input test covers actual NIfTI, DICOM and diffusion-NRRD imports, preview
  without writes, canonical output/manifest creation and parameter-node updates.
- The compact test checks that import controls are under Advanced, remain
  visible when expanded, and retain their action bindings. It also checks EN/ZH
  at 440/540 px and a normal 1280 x 900 window. The collapsed module height is
  now **651 px**, down from 686 px before moving the import row.
- Moving the import panel exposed a CTK visibility regression. Its previous
  collapsible parent retained a visibility event filter after reparenting.
  That filter is removed before moving the panel; the regression test verifies
  the preview and preparation buttons are visible after expansion.

Intermediate failed layout attempts are retained in the same validation root;
the final acceptance run uses the final source snapshot. This is UI acceptance,
not a repeat of the full scientific processing campaign. Scientific acceptance
and its limits remain documented in `SLICER_ACCEPTANCE_20261007.md`.

## Live Session

The deployed module is running in `slicerdsurfer-current-20260928` at
`http://127.0.0.1:6086/vnc.html`. Its module tree was refreshed in copy mode.
The panel is initially 480 px wide and can still be resized by the user.

The dedicated session's selector previously explicitly resized the main window
to 1800 x 1100, filling its virtual desktop. It was neither maximized nor in
full-screen mode. The selector now uses `showNormal()`, 1280 x 900 and position
(40, 30). Data Probe starts collapsed in this dedicated session so the Run button
and log fit; neither Slicer's global fonts/DPI nor MRI Agent settings are changed.

Before restarting this session, its pipeline was confirmed inactive with no
loaded volume data, its scene was saved to
`/tmp/slicerdds-home-no-stripes-20260928/ui_before_20261008.mrb`, and its extension,
selector and configuration were backed up under
`ignore/validation/ui_compact_20261008/live_*_before`.

Live verification confirmed the Beginner section is hidden, Advanced is
collapsed, language is in the header and the new module path is in use.
The noVNC endpoint returned HTTP 200. Live evidence:
`ignore/validation/ui_compact_20261008/live_verified.json` and `live_after.png`.

The follow-up was applied to the running session without restarting it or
clearing its scene. Live measurements confirm a 1280 x 900 non-fullscreen,
non-maximized window, a resizable 480 px module panel, hidden/collapsed import
controls under Advanced and visible Run/log controls. Evidence:
`ignore/validation/ui_compact_20261008/small_window_live.json` and
`small_window_live.png`.

The MRI Agent container `dmri-chengjin-slicer` on port 6080 was not restarted
or modified; its start timestamp and PID were unchanged. The 6086 container's
pre-existing read-only Slicer settings warnings and disabled-CLI CropVolume
dependency warning remain deployment limitations, separate from this UI change.

No Git commit or push was performed for this UI task.

## Run Button Follow-Up (2026-10-10)

The main action is now **Run SlicerDDSurfer** (Chinese: **运行 SlicerDDSurfer**).
Missing inputs, an empty product selection or incomplete route settings no
longer disable/dim the button. Input validation happens on click, before saving
run settings or performing dependency checks. Missing subject inputs, batch
root or products produce an inline red Waiting message and do not launch a job.
Untouched empty inputs remain neutral. After manual validation, missing-input
feedback stays red until inputs become valid. An active pipeline still disables
the action to prevent duplicate execution, and retains its Cancel control.

Verification: **700 unit tests, 696 passed and 4 skipped**; **3/3 real Slicer GUI
checks passed** (compact UI, run planning and background cancellation). The
compact test includes invalid clicks in English/Chinese, batch input, recovery
to Ready, and assertions that invalid clicks never reach dependency checks.
Evidence is in `ignore/validation/run_button_20261010/`.

The six changed runtime files were backed up and copied to the installed
6086 module. Its Run callback and validation method were refreshed in place;
no scene nodes, input values or scientific outputs were changed. The live
session verified the bright button, new label and red Waiting feedback. The
MRI Agent container on 6080 was not modified or restarted.

### Focused UI Commit Validation

The UI-only commit includes the compact layout, Run validation, localization,
status/log styling and their regression tests. Algorithm, model, shutdown/setup
and other scientific changes in the working tree are intentionally excluded.
Run remains protected through result loading before it is re-enabled.

An independent export of the staged Git tree passed **669 unit tests**
(**665 passed, 4 skipped**), including **45 targeted UI tests**, and the real
Slicer compact-UI smoke test. Evidence:
`ignore/validation/run_button_push_20261010/staged_unit_tests.log` and
`ignore/validation/run_button_push_20261010/gui/gui_acceptance.json`.
The earlier 700-test result refers to the full local working tree, not this
focused commit. Only the isolated GUI test runner/bootstrap were copied into
the exported test harness; neither changes the tested runtime module sources.
