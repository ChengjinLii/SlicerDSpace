---
name: slicerddsurfer-install
description: Install, enable and verify SlicerDDSurfer for a user through their local Agent, using an authorized checkout and existing 3D Slicer. Use for first installation or an explicitly requested upgrade, not for diagnosing scientific results.
---

# Install And Enable SlicerDDSurfer

Use the project's installer and Slicer's own APIs. Keep installation, dependency
readiness and scientific QC as three distinct outcomes. The verified reference
version is Slicer 5.10 on Linux; consult the support matrix for other platforms.

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
`<install-root>/SlicerDDSurfer/lib/Slicer-<major>.<minor>/qt-scripted-modules`.
Check that it contains `SlicerDDSurfer.py`, runtime resources and the staging
manifest at the extension root. Never replace this with a copy of the entire
development repository. Use `--clean` only for an approved upgrade of this exact
staged extension, after retaining its previous manifest/settings.

To verify in a fresh Slicer process, set these environment variables:

| Variable | Value |
| --- | --- |
| `SLICERDDSURFER_AGENT_MODULE_DIR` | Absolute staged module directory |
| `SLICERDDSURFER_AGENT_RECEIPT` | Writable JSON receipt path |
| `SLICERDDSURFER_AGENT_PERSIST` | `1` only if the user requests persistent enablement |
| `SLICERDDSURFER_AGENT_EXIT` | `1` for an isolated test process; otherwise omit |

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

In Slicer, select the intended products, then use **Environment and installation
> Prepare selected analysis environment**. The plugin discovers installed
extensions and prepares supported dependencies/resources. Ask for the user's
approval of downloads, licenses and necessary restarts. Never accept FSL/PNL or
FreeSurfer terms on the user's behalf. Recheck after a restart.

Start with the user's chosen route, or offer DTI as a minimal installation check.
Do not default to installing every backend. CLI checks use the same selections:

```bash
/path/to/Slicer --launch PythonSlicer /path/to/repo/run_subject_pipeline.py \
  --no-user-config --subject-root /path/to/subject \
  --targets validation,microstructure --microstructure-stages dti --doctor
```

`--doctor` reports readiness; it is not an instruction to run patient data.
Use `--plan` before an explicitly requested analysis. See
`docs/setup/MANAGED_SETUP.md` for repair/offline import and
`docs/setup/QUICKSTART.md` for bundle-source and model-concurrency options.

## Finish Or Stop

Report the checkout revision, Slicer version, install path, activation receipt,
whether settings persist, and remaining dependency/restart actions. Link the
receipt and logs. If a helper fails, preserve its report and fix the specific
cause; do not repeatedly reinstall, delete unrelated environments or substitute
algorithms. If runtime readiness or real-data QC was not checked, say so plainly.
