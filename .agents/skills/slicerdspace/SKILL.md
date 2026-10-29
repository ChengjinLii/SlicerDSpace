---
name: slicerdspace
description: Install, enable and use SlicerDSpace through a local Agent. Prepare diffusion inputs, select analysis routes, validate CLI plans, run requested analyses or experiments, and inspect recorded results and QC. Installation alone does not authorize scientific runs or certify anatomical correctness.
---

# SlicerDSpace Workflow

Use the project's installer and Slicer's own APIs. Keep installation, dependency
readiness and scientific QC as three distinct outcomes. The verified reference
version is Slicer 5.10 on Linux; consult the support matrix for other platforms.

## Choose The Requested Mode

- **Install/upgrade:** follow the installation steps below. Stop after activation
  and requested dependency preparation unless analysis is also requested.
- **Use/analyze:** if the module already works, do not reinstall it. Read
  [the usage workflow](references/usage.md), then select the relevant
  [algorithm Shell template](references/shell_templates.md).
- **Compare/batch:** use the same usage workflow and
  `docs/setup/EXPERIMENTS.md`; freeze per-variant settings before submitting.

Project-relative paths below refer to the authorized checkout or installed
runtime root containing `shared/` and `scripts/`, not this skill's directory.
Use the skill name `slicerdspace`.
Read this `SKILL.md` as the entry point. When installing or copying the Skill,
preserve its complete directory, including `references/`, `scripts/`, `assets/`
and `agents/`; the entry Markdown file alone does not include those resources.

## Inspect First

- Find the user's Slicer launcher, OS/architecture, installed Slicer version,
  authorized checkout and intended install location. Never invent credentials,
  download a different Slicer, or change drivers to make installation succeed.
- If starting from a web link, obtain an authorized checkout before using its
  scripts or relative references. If the private repository is inaccessible,
  request access or a local checkout rather than treating the page as a missing
  software dependency.
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

## Confirm Model And Resource Storage

Before downloading model weights, atlases or other large resources, establish
where the user wants them stored. Keep them outside the staged extension so an
upgrade does not remove them. Apply this storage-choice step even when the
user's installation request does not mention storage paths.

- If the user already gives a path, validate and use it; do not ask them to
  choose again. Otherwise, inspect the saved `external_dependencies.model_assets_dir`,
  `SLICERDSPACE_MODEL_ASSETS_DIR` and the platform-specific root returned by
  `shared.model_assets.default_user_model_assets_root()`. Check user-approved
  data locations or mounted user storage for an alternative with more space.
  Limit discovery to these locations, without searching unrelated medical data
  or accepting another account's cache as trusted.
- Offer two or three usable candidates when available, using absolute paths.
  For each, show available disk space, writability, whether verified assets can
  be reused and the reason to choose it. Identify the recommended option. If
  only one is usable, explain that instead of inventing alternatives. Allow a
  custom path. For a new directory, assess the nearest existing parent first.
- Ask the user to select the model-storage location and **wait for their answer
  before creating it, moving files or downloading resources**. A recommendation
  or a preselected option is not confirmation. Do not silently choose the
  default, a developer-specific path, the system drive or the largest disk.
- For the chosen analyses, use `models/assets_manifest.json` and the optional
  resource manifests to estimate remaining download and extraction space.
  Check that external backends can access the path, including Windows/WSL path
  mapping when needed. Reuse existing resources only after manifest verification;
  do not download every profile or move an existing cache without approval.
- Save the selected absolute root as `external_dependencies.model_assets_dir`
  using `shared.user_config.update_user_config`, preserving the other settings.
  The GUI's **Environment and installation > More options > Model assets root**
  uses this setting. Use the same root for downloader `--asset-root` and analysis
  `--model-assets-dir`. Check for a conflicting `SLICERDSPACE_MODEL_ASSETS_DIR`;
  use the confirmed root for the setup process and subsequent launch, without
  editing global shell profiles or system environment variables unasked.

If later analysis requests need additional resources, reuse the confirmed root
and ask about the new downloads/terms; ask for a new location only when the user
requests it or the existing root is no longer suitable.

## Prepare Only Requested Analyses

If the user prioritizes fewer external environments, read
`docs/setup/EXPERIMENTS.md` and offer the explicit Slicer-native preset before
preparing dependencies. It selects different masking/tracking methods; explain
that tradeoff and do not change PNL/CSD selections without approval. Existing
valid supplied masks avoid automatic extraction altogether.

In Slicer, select the intended products, then use **Environment and installation
> Prepare selected analysis environment**. The plugin discovers installed
extensions and prepares supported dependencies/resources. Confirm the model and
resource root above before starting preparation. Ask for the user's
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

## Algorithm Code Templates

Use [references/shell_templates.md](references/shell_templates.md) for the full
code catalogue and `assets/shell/*.sh` for standalone Bash templates. Read only
the requested route and its prerequisites, not every algorithm at once.

| Section | Algorithms and variants |
| --- | --- |
| [Masks](references/shell_templates.md#brain-masks) | PNL CNN, DIPY, MRtrix, SynthStrip |
| [Preprocessing](references/shell_templates.md#preprocessing) | DIPY MP-PCA/Local PCA/Patch2Self; MRtrix/FSL |
| [Anatomical prior](references/shell_templates.md#anatomical-prior) | DDSeg, DDParcel, DDSurfer, native cortical postprocessing |
| [Microstructure](references/shell_templates.md#microstructure) | DTI WLS/OLS, FW, NODDI, DKI WLS/OLS, Python MK-Curve, optional MATLAB reference |
| [Tractography](references/shell_templates.md#tractography) | DTI deterministic, UKF, CSD/ACT with SIFT2, SAF |
| [Fiber bundles](references/shell_templates.md#fiber-bundles) | WMQL, WMA, TractCloud; source selection and combinations |
| [Connectome](references/shell_templates.md#connectome-and-combined-routes) | Python count/scalar-weighted or MRtrix/SIFT2; combined routes |

Set the actual Slicer, runtime, subject, output and confirmed resource paths as
shown in the catalogue. The Skill directory and `REPO` are separate locations:
`REPO` can be an installed extension runtime even when this Skill is elsewhere.

```bash
export SKILL="/absolute/path/to/slicerdspace"
bash "$SKILL/assets/shell/ddparcel.sh" doctor
bash "$SKILL/assets/shell/ddparcel.sh" plan
# Only after the user confirms the plan:
bash "$SKILL/assets/shell/ddparcel.sh" execute
```

Omitting the mode means `plan`. Use the same script/settings for all three
modes. `--help` needs no Slicer or data. Additional scientific options belong in
a separate edited script copy, not positional arguments to the template.
Use `DEPENDENCY_CONFIG` for saved GUI dependency paths. The catalogue also
links input import, cohort, parameter-experiment, regional and report commands;
those have their own preview/authorization semantics.

The standalone scripts are generated from `docs/setup/CLI_TEMPLATES.md`, not
independent implementations of the algorithms. Update that guide and its
Chinese counterpart first, then run `python scripts/build_skill_shell_templates.py`.
`--check` detects missing, edited or stale generated files. Do not regenerate or
overwrite a user's customized copy during an installation or analysis.

## Finish Or Stop

For installation, report the checkout revision, Slicer version, install path,
confirmed model/resource root, prepared resource profiles, activation receipt,
persistence and remaining dependency/restart actions.
For analyses, report methods, output/run/report paths, QC and review items as
described in the usage workflow. If a helper fails, preserve its report and fix the specific
cause; do not repeatedly reinstall, delete unrelated environments or substitute
algorithms. If runtime readiness or real-data QC was not checked, say so plainly.
