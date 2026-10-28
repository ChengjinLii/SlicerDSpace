<div align="center">

# Surface Postprocessing Components

**Optional source-built tools, without a full FreeSurfer installation**

[Project](../../README.md) | [Setup](QUICKSTART.md) | [Platforms](SUPPORT_MATRIX.md) | [中文](SURFACE_COMPONENTS.zh-CN.md)

</div>

DDSurfer snapshot `8a8699c0fda32be7e0a3cbca2903680b9f0c950b` supports surface
postprocessing using seven locally compiled original FreeSurfer commands.
This is native-code reuse, not a Python rewrite, a new numerical method or a
replacement for the complete FreeSurfer suite. Postprocessing remains optional.

---

## Choose A Route

| Configuration | Behavior |
| --- | --- |
| Surface component path supplied | Use that source-built runtime, without discovering the full suite |
| No component path; existing FreeSurfer detected | Reuse the existing installation |
| Neither supplied | Look for the upstream recipe-matched user cache |

Use **Environment and installation > More options > advanced paths** to set
the optional component directory and your personal activation file. Keep the
component path empty to use an existing FreeSurfer installation instead.
`SLICERDSPACE_SURFACE_RUNTIME` also selects a local runtime; `FS_LICENSE`
selects a personal activation file. An explicitly selected incomplete/corrupt
runtime is an error, not a reason to fall back silently.

The current indexed native `lh/rh.white.obj` and `lh/rh.pial.obj` route is
supported. The historical STL/external-shell route is not converted to a
seven-command backend: it has additional dependencies and a different contract.

---

## First Preparation

**Check never downloads or compiles. Run never prepares a compiler silently.**
After checking the selected analysis, use **Prepare selected environment**.
When local components are missing, the confirmation explains the source/data
terms and requests approval before starting a cancellable background build.
The successful receipt saves the component path automatically. A missing
personal activation file remains a separate manual requirement, not a rebuild.

Source building needs Git, C/C++ compilers, system development libraries
(including crypt on the tested Linux system), and **CMake >=3.24,<4**. The plugin
does not install system compilers or change Slicer's Python/driver/shell. If the
tools are absent, install them first; an alternative is to configure a previously
built component directory or existing FreeSurfer. First-use source downloads and
build trees require additional disk space and may take several minutes or longer.

CLI preparation, with explicit agreement to applicable source/data terms:

```bash
python scripts/setup_surface_runtime.py --execute --accept-terms --jobs 4
```

Use `--cmake /path/to/cmake` when CMake is not on PATH. `--work-dir`, `--prefix`,
`--source-root` and `--offline` support controlled preparation. Offline mode
requires the atlas profile, pinned Git source and checked dependency archives
to be cached already. Without `--execute`, the command only prints its plan.
Existing corrupt or differently built prefixes are not overwritten.

The unchanged upstream builder compiles the pinned FreeSurfer revision,
ITK Common/VNL and zlib. The adapter only relocates atlas data to the shared
user asset directory. Its 29,657,074-byte archive is downloaded from a pinned
DDSurfer commit and SHA256-verified; it is not part of the extension package,
and this change does not claim it has been uploaded to SlicerDDSurfer-models.
The component runtime remains in the upstream recipe-addressed user cache
unless an explicit prefix is supplied.

---

## Run And Verify

```bash
python run_subject_pipeline.py --subject-root /data/sub-01 --subject-id sub-01 \
  --targets surface_postprocess --postprocess-runtime /data/local-components \
  --postprocess-license-file /data/private/freesurfer-license.txt --execute
```

Use the same subject root containing the reconstructed native OBJ masters, or
provide `--postprocess-native-dir`. `--postprocess-freesurfer-home` remains
available for the full-installation route. SynthStrip and its model are separate;
the seven surface commands do not supply masking.

The component manifest, source revision, library availability and checksums are
verified in an isolated worker. The activation precheck tests file presence,
not a license grant; the original tools still perform their activation checks.
Output geometry, morphometry and annotation integrity are checked separately.
QC success does not replace anatomical review. Runtime identity is recorded in
the manifest and cache signature; switching an explicit runtime prevents reuse
of the previous runtime's completion state.

Automatic source preparation is currently **Linux x86_64 only**. macOS source
compilation and native Windows are not certified; Windows/WSL is not equivalent
to native Windows support. Existing platform-native FreeSurfer remains an
alternative where supported. No end-to-end computation speedup is claimed.

---

## Attribution

The FreeSurfer commands and atlases retain the
[FreeSurfer agreement](../../licenses/FreeSurfer.txt) and third-party terms.
The pinned backend also includes its [data notices](../../anatomy/surface/ddsurfer_backend/postprocessing/assets/LICENSE.txt).
Personal activation files are never included in packages, model mirrors or
automatic downloads. See [implementation provenance](../architecture/IMPLEMENTATION_PROVENANCE.md).
