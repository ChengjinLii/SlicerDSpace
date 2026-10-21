<div align="center">

# Algorithm Selection And Compact Settings

**21 October 2026 · Native Slicer GUI and workflow integration**

[Project](../../README.md) | [Quick Start](../setup/QUICKSTART.md) | [Managed Setup](../setup/MANAGED_SETUP.md) | [中文](ALGORITHM_SELECTION_20261021.zh-CN.md)

</div>

---

## User Interface

Microstructure, Tractography and Bundles each have a matching **Select…**
button on the main screen. Check one or several algorithms, then Apply.
Cancel preserves the previous selection. Empty selections are not accepted.
The current algorithms remain visible beside the product checkbox, with wrapping
text rather than a wider dock. Selections persist in MRML and shared user settings.

| Product | Available choices | Default |
| --- | --- | --- |
| Microstructure | DTI, Free-water, NODDI, DKI | DTI; retained as required preparation |
| Tractography | MRtrix3 CSD/ACT, official UKF, DTI deterministic, CSD + SAF | CSD/ACT |
| Bundles | WMQL, WMA, TractCloud; arbitrary nonempty combinations | WMQL |

Advanced settings shows one category at a time: preprocessing/mask, model
parameters, run/performance, or regions/input import. Relevant controls still
depend on the selected methods. Legacy bound selectors remain hidden for
configuration compatibility. Environment installation and Results/QC are
independent sections, not nested inside Advanced settings.

---

## Execution And Safety

Multiple tracking methods run sequentially in separate `<run>__<backend>`
variants. Shared requested anatomy and microstructure stages are scheduled once.
Selected bundle methods and connectomes operate on each tracking variant;
tractograms are never combined. This is not a new scientific tracking algorithm.
Multiple methods require additional time, dependencies and storage.

UKF retains its own author parameters and official executable discovery;
CSD streamline counts do not control UKF density. Missing dependencies and
failed acquisition/QC checks remain blocking conditions. One failed variant
cannot be reported as an entirely successful comparison.

Each child has its own manifest, with an aggregate manifest for the selection.
Automatic display resolves actually started, fresh child manifests, including
batch runs. It does not scan output directories or use planned/stale child records.
Bundle QC validation recognizes variant-qualified task names; suffixes cannot
bypass a failed bundle QC gate.

CLI example for planning, not processing:

```bash
python3 run_subject_pipeline.py --subject-root /path/to/subject \
  --targets validation,microstructure,tractography,bundles,connectome \
  --microstructure-stages dti,noddi \
  --tractography-backend csd_act,ukf --bundle-backend wmql,tractcloud --plan
```

---

## Verification Scope

The full Python regression suite ran 1,267 tests: 1,264 passed, three skipped.
Native Slicer 5.10 checks covered the actual multi-select dialogs, Apply/Cancel,
shared configuration persistence, algorithm labels, dependency preparation,
regional analysis and compact English/Chinese layouts at 440/540 pixels.
A separate two-process mask GUI test passed 109 selection and 59 restoration
checks after the layout change. The runtime package resource audit and active
documentation/metadata checks passed.

Private evidence is under `ignore/validation/algorithm_picker_20261021/`:
`tests-complete.log`, `gui-final/`, `brain-mask/` and the CLI plan log. These are engineering
checks, not new full-brain multi-algorithm scientific acceptance or cross-platform
GUI validation. Existing acquisition requirements, scientific validity masks,
anatomical-review obligations and platform limits are unchanged.
