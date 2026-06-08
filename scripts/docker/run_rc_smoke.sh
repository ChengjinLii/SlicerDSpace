#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-slicerddsurfer-rc-smoke:ubuntu22.04}"
DEFAULT_REPO_URL="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)"
REPO_URL="${REPO_URL:-${DEFAULT_REPO_URL:-https://github.com/ChengjinLii/SlicerDDSurfer.git}}"
REPO_REF="${REPO_REF:-main}"
HOST_SOFTWARE_ROOT="${HOST_SOFTWARE_ROOT:-/data/chengjin/software}"
HOST_SLICER_LAUNCHER="${HOST_SLICER_LAUNCHER:-$HOST_SOFTWARE_ROOT/run-slicer.sh}"
HOST_MRTRIX_BIN="${HOST_MRTRIX_BIN:-$HOST_SOFTWARE_ROOT/mrtrix3_env/bin}"
HOST_WORK_ROOT="${HOST_WORK_ROOT:-/tmp/slicerddsurfer-rc-smoke}"
DOCKER_NETWORK="${DOCKER_NETWORK:-bridge}"
KEEP_WORK="${KEEP_WORK:-0}"
HOST_SSH_DIR="${HOST_SSH_DIR:-$HOME/.ssh}"
MOUNT_SSH="${MOUNT_SSH:-auto}"
HOST_SSH_IDENTITY_FILE="${HOST_SSH_IDENTITY_FILE:-}"
SMOKE_STAGE="${SMOKE_STAGE:-install}"
if [[ -z "${SMOKE_LFS_MODE:-}" ]]; then
  if [[ "$SMOKE_STAGE" == "quick-gate" ]]; then
    SMOKE_LFS_MODE="full"
  else
    SMOKE_LFS_MODE="quick"
  fi
fi
SMOKE_SUBJECT_ID="${SMOKE_SUBJECT_ID:-100307-release-candidate}"
SMOKE_RUN_NAME="${SMOKE_RUN_NAME:-rc_csd_act}"
SMOKE_TARGETS="${SMOKE_TARGETS:-validation,preprocessing,segmentation,parcellation,surface,microstructure,tractography,bundles,connectome}"
SMOKE_BUNDLE_BACKEND="${SMOKE_BUNDLE_BACKEND:-all}"
SMOKE_SELECT_STREAMLINES="${SMOKE_SELECT_STREAMLINES:-100000}"
HOST_SUBJECT_INPUT_ROOT="${HOST_SUBJECT_INPUT_ROOT:-/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/input}"
HOST_TRACT_QUERIER_ROOT="${HOST_TRACT_QUERIER_ROOT:-}"

if [[ ! -f "$SCRIPT_DIR/rc-smoke.Dockerfile" ]]; then
  echo "Missing Dockerfile: $SCRIPT_DIR/rc-smoke.Dockerfile" >&2
  exit 2
fi
if [[ ! -x "$HOST_SLICER_LAUNCHER" ]]; then
  echo "HOST_SLICER_LAUNCHER is not executable: $HOST_SLICER_LAUNCHER" >&2
  exit 2
fi
if [[ ! -d "$HOST_MRTRIX_BIN" ]]; then
  echo "HOST_MRTRIX_BIN is not a directory: $HOST_MRTRIX_BIN" >&2
  exit 2
fi
case "$SMOKE_STAGE" in
  install|quick-gate)
    ;;
  *)
    echo "SMOKE_STAGE must be install or quick-gate, got: $SMOKE_STAGE" >&2
    exit 2
    ;;
esac
case "$SMOKE_LFS_MODE" in
  quick|full)
    ;;
  *)
    echo "SMOKE_LFS_MODE must be quick or full, got: $SMOKE_LFS_MODE" >&2
    exit 2
    ;;
esac
if [[ "$SMOKE_STAGE" == "quick-gate" ]]; then
  if [[ "$SMOKE_LFS_MODE" != "full" ]]; then
    echo "SMOKE_STAGE=quick-gate requires SMOKE_LFS_MODE=full so model/data LFS objects are available." >&2
    exit 2
  fi
  if [[ ! -d "$HOST_SUBJECT_INPUT_ROOT" ]]; then
    echo "HOST_SUBJECT_INPUT_ROOT is not a directory: $HOST_SUBJECT_INPUT_ROOT" >&2
    exit 2
  fi
  for required in data.nii.gz bvals bvecs nodif_brain_mask.nii.gz; do
    if [[ ! -f "$HOST_SUBJECT_INPUT_ROOT/$required" ]]; then
      echo "Missing quick-gate input: $HOST_SUBJECT_INPUT_ROOT/$required" >&2
      exit 2
    fi
  done
fi
if [[ -n "$HOST_TRACT_QUERIER_ROOT" && ! -d "$HOST_TRACT_QUERIER_ROOT" ]]; then
  echo "HOST_TRACT_QUERIER_ROOT is not a directory: $HOST_TRACT_QUERIER_ROOT" >&2
  exit 2
fi

case "$HOST_WORK_ROOT" in
  /tmp/*|/var/tmp/*|"$REPO_ROOT"/.docker-smoke-work*)
    ;;
  *)
    echo "Refusing to clean HOST_WORK_ROOT outside /tmp, /var/tmp, or repo .docker-smoke-work: $HOST_WORK_ROOT" >&2
    exit 2
    ;;
esac

if [[ "$KEEP_WORK" != "1" ]]; then
  if [[ -e "$HOST_WORK_ROOT" ]] && ! rm -rf "$HOST_WORK_ROOT" 2>/dev/null; then
    echo "[rc-smoke] Cleaning root-owned workdir remnants via a disposable ubuntu:22.04 container"
    docker run --rm --network none \
      -e TARGET_BASENAME="$(basename "$HOST_WORK_ROOT")" \
      -v "$(dirname "$HOST_WORK_ROOT"):/host_parent" \
      ubuntu:22.04 \
      sh -c 'rm -rf -- "/host_parent/$TARGET_BASENAME"'
  fi
fi
mkdir -p "$HOST_WORK_ROOT"

echo "[rc-smoke] Building $IMAGE_NAME"
docker build \
  -f "$SCRIPT_DIR/rc-smoke.Dockerfile" \
  -t "$IMAGE_NAME" \
  "$SCRIPT_DIR"

echo "[rc-smoke] Running fresh-clone install smoke"
DOCKER_RUN_ARGS=(
  --rm
  --network "$DOCKER_NETWORK" \
  -e REPO_URL="$REPO_URL" \
  -e REPO_REF="$REPO_REF" \
  -e SMOKE_STAGE="$SMOKE_STAGE" \
  -e HOST_SLICER_LAUNCHER="$HOST_SLICER_LAUNCHER" \
  -e HOST_MRTRIX_BIN="$HOST_MRTRIX_BIN" \
  -e SMOKE_LFS_MODE="$SMOKE_LFS_MODE" \
  -e SMOKE_SUBJECT_ID="$SMOKE_SUBJECT_ID" \
  -e SMOKE_RUN_NAME="$SMOKE_RUN_NAME" \
  -e SMOKE_TARGETS="$SMOKE_TARGETS" \
  -e SMOKE_BUNDLE_BACKEND="$SMOKE_BUNDLE_BACKEND" \
  -e SMOKE_SELECT_STREAMLINES="$SMOKE_SELECT_STREAMLINES" \
  -e GIT_TERMINAL_PROMPT=0 \
  -e HOME=/work/home \
  -e XDG_CACHE_HOME=/work/home/.cache \
  -e XDG_CONFIG_HOME=/work/home/.config \
  -v "$HOST_SOFTWARE_ROOT:$HOST_SOFTWARE_ROOT:ro" \
  -v "$HOST_WORK_ROOT:/work" \
)
if [[ "$SMOKE_STAGE" == "quick-gate" ]]; then
  DOCKER_RUN_ARGS+=(
    -v "$HOST_SUBJECT_INPUT_ROOT:/inputs/$SMOKE_SUBJECT_ID/input:ro"
  )
fi
if [[ -n "$HOST_TRACT_QUERIER_ROOT" ]]; then
  DOCKER_RUN_ARGS+=(
    -v "$HOST_TRACT_QUERIER_ROOT:/external/tract_querier:ro"
    -e CONTAINER_TRACT_QUERIER_ROOT=/external/tract_querier
  )
fi
if [[ "$MOUNT_SSH" == "1" || ( "$MOUNT_SSH" == "auto" && "$REPO_URL" == git@* && -d "$HOST_SSH_DIR" ) ]]; then
  if [[ -z "$HOST_SSH_IDENTITY_FILE" ]]; then
    for candidate in "$HOST_SSH_DIR/id_ed25519" "$HOST_SSH_DIR/id_rsa" "$HOST_SSH_DIR/id_ecdsa"; do
      if [[ -f "$candidate" ]]; then
        HOST_SSH_IDENTITY_FILE="$candidate"
        break
      fi
    done
  fi
  if [[ ! -f "$HOST_SSH_IDENTITY_FILE" ]]; then
    echo "Could not find SSH identity for private Git clone. Set HOST_SSH_IDENTITY_FILE." >&2
    exit 2
  fi
  SSH_IDENTITY_BASENAME="$(basename "$HOST_SSH_IDENTITY_FILE")"
  echo "[rc-smoke] Mounting SSH credentials read-only for private Git clone: $HOST_SSH_DIR"
  DOCKER_RUN_ARGS+=(
    -v "$HOST_SSH_DIR:/ssh:ro"
    -e GIT_SSH_COMMAND="ssh -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/work/known_hosts -i /ssh/$SSH_IDENTITY_BASENAME"
  )
fi

docker run "${DOCKER_RUN_ARGS[@]}" \
  "$IMAGE_NAME" \
  bash -lc '
set -euo pipefail
mkdir -p /work/home /work/src /work/install /work/logs
echo "[container] repo=$REPO_URL ref=$REPO_REF"
echo "[container] stage=$SMOKE_STAGE"
echo "[container] slicer=$HOST_SLICER_LAUNCHER"
echo "[container] mrtrix=$HOST_MRTRIX_BIN"
echo "[container] lfs_mode=$SMOKE_LFS_MODE"
test -x "$HOST_SLICER_LAUNCHER"
test -x "$HOST_MRTRIX_BIN/mrconvert"
if [[ -d /work/src/SlicerDDSurfer/.git ]]; then
  echo "[container] Reusing existing checkout: /work/src/SlicerDDSurfer"
else
  GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none "$REPO_URL" /work/src/SlicerDDSurfer
fi
cd /work/src/SlicerDDSurfer
FETCHED_REF=0
if [[ -d .git ]]; then
  git remote set-url origin "$REPO_URL"
  if git fetch --depth=1 origin "$REPO_REF" || git fetch origin "$REPO_REF"; then
    FETCHED_REF=1
  fi
fi
if [[ "$FETCHED_REF" == "1" ]]; then
  git checkout --detach FETCH_HEAD
else
  git checkout "$REPO_REF"
fi
git lfs install --local
case "$SMOKE_LFS_MODE" in
  quick)
    echo "[container] Quick LFS mode: auditing pointer metadata without downloading large objects"
    git lfs ls-files -s | tee /work/logs/git_lfs_ls_files.txt
    python3 scripts/release_audit.py | tee /work/logs/release_audit.txt
    ;;
  full)
    echo "[container] Full LFS mode: downloading all LFS objects; this can be slow on constrained networks"
    GIT_LFS_PROGRESS=/work/logs/git-lfs-progress.log git lfs pull
    git lfs fsck
    ;;
esac
case "$SMOKE_STAGE" in
  install)
    python3 scripts/stage_slicer_extension.py \
      --install-root /work/install \
      --clean \
      --link-mode copy | tee /work/logs/stage_slicer_extension.json
    MODULE_DIR=/work/install/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules
    test -f "$MODULE_DIR/SlicerDDSurfer.py"
    env \
      SLICERDDSURFER_EXTENSION_MODULE_DIR="$MODULE_DIR" \
      PATH=/usr/bin:/bin \
      xvfb-run -a -s "-screen 0 1280x1024x24" \
      "$HOST_SLICER_LAUNCHER" --no-splash \
      --additional-module-paths "$MODULE_DIR" \
      --python-script /work/src/SlicerDDSurfer/Testing/Python/slicer_extension_install_smoke.py \
      2>&1 | tee /work/logs/slicer_extension_install_smoke.log
    echo "[container] RC_SMOKE_OK"
    ;;
  quick-gate)
    SUBJECT_ROOT="/work/subject/$SMOKE_SUBJECT_ID"
    OUTPUT_ROOT="/work/outputs/$SMOKE_SUBJECT_ID"
    mkdir -p "$SUBJECT_ROOT" "$OUTPUT_ROOT"
    rm -f "$SUBJECT_ROOT/input"
    ln -s "/inputs/$SMOKE_SUBJECT_ID/input" "$SUBJECT_ROOT/input"
    QUICK_GATE_ARGS=(
      /work/src/SlicerDDSurfer/run_subject_pipeline.py
      --subject-root "$SUBJECT_ROOT"
      --subject-id "$SMOKE_SUBJECT_ID"
      --output-root "$OUTPUT_ROOT"
      --targets "$SMOKE_TARGETS"
      --tractography-backend csd_act
      --bundle-backend "$SMOKE_BUNDLE_BACKEND"
      --microstructure-stages dti
      --run-name "$SMOKE_RUN_NAME"
      --mrtrix-bin-dir "$HOST_MRTRIX_BIN"
      --select-streamlines "$SMOKE_SELECT_STREAMLINES"
      --preprocessing-dipy-denoise-method none
      --preprocessing-skip-gibbs
      --preprocessing-skip-motion
      --execute
      --print-manifest-only
    )
    if [[ -n "${CONTAINER_TRACT_QUERIER_ROOT:-}" ]]; then
      QUICK_GATE_ARGS+=(--tract-querier-root "$CONTAINER_TRACT_QUERIER_ROOT")
    fi
    "$HOST_SLICER_LAUNCHER" --launch PythonSlicer "${QUICK_GATE_ARGS[@]}" \
      2>&1 | tee /work/logs/100307_quick_gate.log
    MANIFEST_PATH="$OUTPUT_ROOT/00_run_metadata/${SMOKE_RUN_NAME}_orchestration_manifest.json"
    python3 - "$MANIFEST_PATH" <<PY
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
if not manifest_path.is_file():
    raise SystemExit(f"missing quick-gate manifest: {manifest_path}")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
tasks = manifest.get("tasks", [])
by_name = {task.get("name"): task for task in tasks}
failed = [task for task in tasks if task.get("status") == "failed"]
required_completed = (
    "validation",
    "preprocessing.dwi",
    "segmentation.ddseg",
    "parcellation.ddparcel",
    "surface.ddsurfer",
    "microstructure.dti",
    "tractography.csd_act",
    "bundles.wmql",
    "connectome.streamline_count",
    "connectome.sift2_weighted_streamline_count",
)
missing = [name for name in required_completed if name not in by_name]
not_completed = [
    "{}:{}:{}".format(name, by_name[name].get("status"), by_name[name].get("reason", ""))
    for name in required_completed
    if name in by_name and by_name[name].get("status") != "completed"
]
print(f"[quick-gate] manifest={manifest_path}")
print(f"[quick-gate] tasks={len(tasks)} failed={len(failed)} required_not_completed={len(not_completed)}")
if failed:
    raise SystemExit("[quick-gate] failed task(s): " + "; ".join("{}:{}".format(task.get("name"), task.get("reason", "")) for task in failed))
if missing:
    raise SystemExit("[quick-gate] missing required task(s): " + ", ".join(missing))
if not_completed:
    raise SystemExit("[quick-gate] required task(s) not completed: " + "; ".join(not_completed))
PY
    echo "[container] RC_QUICK_GATE_OK"
    ;;
esac
'

echo "[rc-smoke] Logs: $HOST_WORK_ROOT/logs"
