<div align="center">

# GUI Usability And Installed-Session Review

[Project](../../README.md) | [Quickstart](../setup/QUICKSTART.md) | [Managed setup](../setup/MANAGED_SETUP.md) | [中文](GUI_USABILITY_20261021.zh-CN.md)

</div>

---

## Fixes

The scientific acceptance environment was not the interactive Slicer instance.
That instance lacked configured/mounted model and PNL resources, and its installed
SlicerDMRI extension had not loaded the DTI module. Its earlier report had 12
blockers; success elsewhere was not evidence that this session was ready.

Preparation also called `isExtensionLoaded`, which Slicer 5.10 does not expose
through PythonQt. It now checks installed extensions and actual capabilities.
An importable `slicer.util` alone no longer proves native DTI is available.
The dedicated development session's mounts, native extension paths and GPU
visibility were repaired without editing the MRI Agent instance or adding private
server paths to plugin code.

---

## Interaction

- Checks and final preparation verification run in cancellable processes, not the Qt thread.
- Check results appear inline; details open only on request. Ready preparation skips confirmation and installation.
- Offline import, repair and manual paths are under Environment > More options, separate from algorithm settings.
- Run performs background preflight when needed, then continues. Missing dependencies stop submission rather than silently dropping selected products.
- Configuration changes invalidate an in-flight report; cancelled/failed checks do not retain ready cache entries.
- The folder picker fills only an empty subject ID and recognizes a canonical `input/` child. Custom IDs are preserved.
- topup errors open the visible Advanced processing category rather than a hidden legacy section.
- Successful representative results load automatically from the current run; repeat loading with the same policy reuses nodes.

Manual loading may add nonrepresentative maps, which is different from duplicate
nodes. Execution, automated QC and human review remain separate states.

---

## Evidence And Limits

Real Linux Slicer 5.10 tests cover `environment_button`, `environment_async`,
`selected_setup`, `compact_ui`, `algorithm_picker` and `regions`. They exercise
actual Qt controls, MRML bindings, processes, cancellation, stale-report rejection,
dependency blocking and 440/540 px English/Chinese layouts. Isolated tests disable
network access and do not establish first-download reliability.

Python regression: 1,273 tests, 1,270 passed and three skipped. All six GUI
categories passed. A region-test rerun initially collided with an old fixture
directory; it now creates an independent temporary fixture and passed in a new
report directory. The earlier failure was retained, not relabeled as a pass.

The installed session also completed a fresh synthetic-input Run-button journey:
validation passed, DTI and deterministic tracking completed, AD/FA/MD/RD and
streamlines auto-loaded, and repeated automatic loading reused nodes. The check
click returned in approximately 0.081 s. Across the journey, 229 Qt heartbeats
were recorded, with a maximum gap of approximately 1.42 s; fully stall-free
large-result conversion and scene insertion are not claimed.

The current selected-default check reports zero blockers. All 31 core resource
files passed manifest verification; the pinned PNL environment passed actual GPU
forward checks for all three models; a real PyTorch CUDA tensor operation passed.
UKF is unselected and not installed in that session: optional-backend readiness
is not inferred from the default result.

Local evidence: `ignore/validation/algorithm_picker_20261021/gui-final/` and
`gui-regions-final/`, plus `live-ux/`. These include machine-specific paths and are not distributed input data.
This is GUI/integration evidence, not new validation of human anatomy or all
scientific QC. Native Windows/macOS workflows and first-use network failures
still require independent acceptance. SlicerDMRI may emit `No data to glyph!`
while reading tensor-free streamline previews even though line geometry loads;
that native display warning remains open rather than being reported as fixed.
