<div align="center">

# GUI State And Responsiveness

**23 October 2026 | Linux | Slicer 5.10.0**

[Project](../../README.md) | [Release gates](EXTENSION_READINESS.md) | [Log evidence](benchmarks/gui_followup_20261023.json) | [Input evidence](benchmarks/gui_input_inspection_20261023.json) | [中文](GUI_RESPONSIVENESS_20261023.zh-CN.md)

</div>

This follow-up addresses reproduced interface problems, not diffusion-model
changes. No model, fitting method, tractography parameter or QC threshold changed.

---

## Reproduced Problems

A real Slicer GUI test against the preceding code reproduced four failures:
returning to the module overwrote unsaved scene parameters; loading a scene
allowed global recent/default settings to replace saved parameters; incoming
logs interrupted reading by forcing a scroll to the bottom; and a successful
dependency check displayed green readiness despite empty subject inputs.

The corrected version passes all five assertions in the same test, including
the existing behavior of following new logs when already at the bottom.

User defaults now apply only once to a new/reset empty parameter node. Existing
and loaded scenes, including older scenes without the new marker, retain their
values. UI connections are established after restoration; duplicate observer
removal on module re-entry is avoided. Machine-specific external dependency
configuration remains separate from scene analysis parameters.

Finding an input layout now shows a neutral message that dependencies will be
checked on Run. A successful dependency scan does not override missing inputs
or an empty product selection. An unresolvable check-report directory returns
an actionable inline error without launching a worker; a unit test covers this
failure path. Run remains clickable for validation when no job is active.

---

## Log Insertion Measurement

Previously each line crossed PythonQt separately. The new implementation
inserts one HTML chunk for nonempty-line chunks while retaining escaping,
severity colors and the reader's scroll position. A parity test exposed Qt's
empty-paragraph collapsing; chunks containing empty lines retain the original
line-by-line path instead of silently losing blank lines.

| Lines per chunk | Previous median | Batched median | Local speedup |
| --- | --- | --- | --- |
| 500 | 28.07 ms | 9.00 ms | 3.12x |
| 2,000 | 115.02 ms | 35.29 ms | 3.26x |

These are seven post-warm-up repetitions with alternating implementation order
in the same real Slicer/Qt process. Hidden widgets and event-processing exclusion
are identical for both methods. Plaintext and paragraph counts match exactly;
additional empty-line, whitespace, escaping and Chinese-text cases also match.
This measures **GUI log insertion only**, not visible-frame latency, MRI
algorithm performance or total workflow acceleration. The original snapshot's
SHA256 matches `shared/ui_status_log.py` at the recorded base commit.

---

## Validation And Limits

The initial seven isolated GUI scenarios passed: state persistence/readiness, compact EN/ZH
layout, log comparison, real Extension Manager local installation plus native
Self Tests, scene-owned result management/background cancellation, algorithm
multi-selection and asynchronous environment checks. These are project GUI
tests, not seven Slicer-authored scientific tests.

Python regression discovered 1,326 tests: 1,321 passed, five skipped, zero failed.
Metadata, documentation and license-notice integrity checks also passed. Package
audit matched 469 runtime files. This campaign installed a **staging-helper
archive**, not a new SDK/CPack build; the earlier official-build campaign remains
separately recorded and is not relabelled as a test of this revision.

The [evidence record](benchmarks/gui_followup_20261023.json) contains source/test
hashes, baseline failures, final assertions and raw timing samples. Full logs,
screenshots and private profiles remain under
`ignore/validation/gui_followup_20261023/`. Existing DDSurfer and MRI Agent
sessions were not restarted; network access was disabled for GUI tests.

Native Windows/macOS behavior, real-network installation, full scientific
processing and anatomical review were not revalidated here. Large MRML result
loading still needs main-thread work. The changes and this report do not imply
that all remaining workflow performance issues are solved.

---

## Input Directory Follow-Up

Changing unrelated algorithm parameters previously repeated input-directory
inspection, including DICOM header reads. GUI-only reuse now lasts at most one
second between inspections, is limited to one entry per widget and invalidates
on a changed path, subject or shallow filesystem signature. Canonical DWI file
states are inspected explicitly because directory timestamps can miss rapid
changes. Canonical and legacy layouts remain freshly inspected rather than
paying fingerprint overhead. Nested DICOM changes may remain in display feedback
until the next inspection after expiry; this is not an automatic polling service.

Manual validation and Run always bypass reuse. The worker's uncached inspection,
conversion receipt checks, gradient/content validation and scientific QC remain
unchanged. Dependency checks now resolve the actual child subject root before
deciding whether a supplied brain mask exists.

| 20 directory inspections | Original median | GUI path median | Interpretation |
| --- | --- | --- | --- |
| Synthetic DICOM tree, 129 header candidates | 119.70 ms | 9.41 ms | 12.72x less repeated inspection time |
| Canonical DWI layout | 2.27 ms | 2.58 ms | About 0.015 ms extra per call; not a speedup |

Each paired measurement alternates order over seven post-warm-up repetitions
in the same real Slicer process. Layout results match exactly. The DICOM fixture
contains a recognizable header, not a complete clinical acquisition. This does
not measure conversion, scientific algorithm performance or total workflow time.
The first trial's overly general caching slowed canonical input checks to
3.61 ms per 20 calls; the final design avoids that extra fingerprinting. Both
trial and final raw records are retained locally.

Six additional GUI assertions pass: parameter edits cause no extra header reads
after the initial 129 probes; DICOM still requires a missing mask; a Run click
rejects an in-place nested header change before setup; a mask below a parent
directory is found; removing that mask immediately requires its generator; and
removing bvals is immediately rejected without waiting for expiry.

The final campaign reran seven GUI scenarios: input inspection, state persistence,
compact layout, Extension Manager installation plus Self Tests, scene result
management/background cancellation, algorithm multi-selection and asynchronous
environment checks. All passed with isolated settings and no network. Python
regression: **1,336 discovered, 1,331 passed, five skipped, zero failed**.
The staging archive audit matched **470 runtime files**, including the new helper;
this was not a fresh SDK/CPack build. Logs and profiles are under
`ignore/validation/gui_inputs_20261023/`; hashes, measurements and test counts are
in the [input evidence record](benchmarks/gui_input_inspection_20261023.json).

Cold DICOM discovery and large MRML loads still need main-thread work. Neither
this test nor the earlier GUI campaign establishes scientific or cross-platform
acceptance for all algorithms. Existing interactive sessions were left running.
