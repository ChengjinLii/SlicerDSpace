---
name: slicerdspace-install
description: Install, enable and use SlicerDSpace through a local Agent. Prepare diffusion inputs, select analysis routes, validate CLI plans, run requested analyses or experiments, and inspect recorded results and QC. Installation alone does not authorize scientific runs or certify anatomical correctness.
---

# Install And Use SlicerDSpace

Use the project's installer and Slicer's own APIs. Keep installation, dependency
readiness and scientific QC as three distinct outcomes. The verified reference
version is Slicer 5.10 on Linux; consult the support matrix for other platforms.

## Choose The Requested Mode

- **Install/upgrade:** follow the installation steps below. Stop after activation
  and requested dependency preparation unless analysis is also requested.
- **Use/analyze:** if the module already works, do not reinstall it. Read
  [the usage workflow](references/usage.md), then the relevant recipes in the
  checkout's `docs/setup/CLI_TEMPLATES.md` (or its `.zh-CN.md` counterpart).
- **Compare/batch:** use the same usage workflow and
  `docs/setup/EXPERIMENTS.md`; freeze per-variant settings before submitting.

Project-relative paths below refer to the authorized checkout or installed
runtime root containing `shared/` and `scripts/`, not this skill's directory.
Use the skill name `slicerdspace-install`; the former skill directory links here.

## Inspect First

- Find the user's Slicer launcher, OS/architecture, installed Slicer version,
  authorized checkout and intended install location. Never invent credentials,
  download a different Slicer, or change drivers to make installation succeed.
- Read `docs/setup/QUICKSTART.md` and `docs/setup/SUPPORT_MATRIX.md` in the checkout.
  For Windows or macOS, also read the corresponding setup guide.
- Preserve open scenes and other Slicer/Agent sessions. Ask before closing or
  restarting an existing session. A separate test process must use isolated
  settings and a separate display if required.
- Prefer a trusted official extension package when available. Otherwise use the
  source-staging route below; do not describe it as an Extension Manager release.
  Record `git rev-parse HEAD` and local modifications. Do not overwrite a dirty
  checkout or expose a private repository.

## Source Installation

Use a normal Python interpreter for staging. Substitute real paths and the
installed Slicer major/minor version; the example is for Slicer 5.10:

```bash
python3 scripts/stage_slicer_extension.py \
  --install-root /path/to/user/extensions --slicer-version Slicer-5.10 \
  --link-mode copy
```

The module directory is
`<install-root>/SlicerDSpace/lib/Slicer-<major>.<minor>/qt-scripted-modules`.
Check that it contains `SlicerDSpace.py`, runtime resources and the staging
manifest at the extension root. Never replace this with a copy of the entire
development repository. Use `--clean` only for an approved upgrade of this exact
staged extension, after retaining its previous manifest/settings.

To verify in a fresh Slicer process, set these environment variables:

| Variable | Value |
| --- | --- |
| `SLICERDSPACE_AGENT_MODULE_DIR` | Absolute staged module directory |
| `SLICERDSPACE_AGENT_RECEIPT` | Writable JSON receipt path |
| `SLICERDSPACE_AGENT_PERSIST` | `1` only if the user requests persistent enablement |
| `SLICERDSPACE_AGENT_EXIT` | `1` for an isolated test process; otherwise omit |

Launch the actual Slicer executable, not `SlicerApp-real` or an unrelated Python:

```bash
/path/to/Slicer --no-splash \
  --additional-module-paths /absolute/staged/module-directory \
  --python-script /absolute/path/to/this-skill/scripts/enable_in_slicer.py
```

On PowerShell, set variables with `$env:NAME = 'value'` and invoke the executable
with `&`. For a `.app`, use its `Contents/MacOS/Slicer` launcher. Do not pass
shell syntax through a subprocess argument list. Do not use isolated test settings
when the user's intent is to persist activation in their normal profile.

The helper verifies the installed import path, opens the widget and runs the
registered native Self Tests before saving the additional-module path. It refuses
conflicting existing installations. It does not install dependencies, start an
analysis, alter algorithm settings, clear the scene or terminate another process.
Inspect its JSON receipt; launching a process alone is not proof of installation.

## Prepare Only Requested Analyses

If the user prioritizes fewer external environments, read
`docs/setup/EXPERIMENTS.md` and offer the explicit Slicer-native preset before
preparing dependencies. It selects different masking/tracking methods; explain
that tradeoff and do not change PNL/CSD selections without approval. Existing
valid supplied masks avoid automatic extraction altogether.

In Slicer, select the intended products, then use **Environment and installation
> Prepare selected analysis environment**. The plugin discovers installed
extensions and prepares supported dependencies/resources. Ask for the user's
approval of downloads, licenses and necessary restarts. Never accept FSL/PNL or
FreeSurfer terms on the user's behalf. Recheck after a restart.

Start with the user's chosen route, or offer DTI as a minimal installation check.
Do not default to installing every backend. CLI checks use the same selections:

```bash
/path/to/Slicer --launch PythonSlicer /path/to/runtime/shared/run_subject_pipeline_cli.py \
  --no-user-config --subject-root /path/to/subject \
  --targets validation,microstructure --microstructure-stages dti --doctor
```

`--doctor` reports readiness; it is not an instruction to run patient data.
Use `--plan` before an explicitly requested analysis. See
`docs/setup/MANAGED_SETUP.md` for repair/offline import and
`docs/setup/CLI_TEMPLATES.md` for full route commands, source selection,
model concurrency, batch execution and result inspection.

## Use After Installation

Follow [references/usage.md](references/usage.md) for input staging, route
selection, device/resource planning, GUI/CLI execution, cancellation and review.
The project's templates default to `--plan`. Retain identical scientific
arguments for `--doctor`, `--plan` and the authorized `--execute` run. Preserve
the selected method when dependencies or acquisition checks fail; explain the
specific blocker instead of substituting a method or relaxing QC thresholds.

## Finish Or Stop

For installation, report the checkout revision, Slicer version, install path,
activation receipt, persistence and remaining dependency/restart actions.
For analyses, report methods, output/run/report paths, QC and review items as
described in the usage workflow. If a helper fails, preserve its report and fix the specific
cause; do not repeatedly reinstall, delete unrelated environments or substitute
algorithms. If runtime readiness or real-data QC was not checked, say so plainly.
