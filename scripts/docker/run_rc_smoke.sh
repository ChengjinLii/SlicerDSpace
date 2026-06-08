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
SMOKE_LFS_MODE="${SMOKE_LFS_MODE:-quick}"

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
case "$SMOKE_LFS_MODE" in
  quick|full)
    ;;
  *)
    echo "SMOKE_LFS_MODE must be quick or full, got: $SMOKE_LFS_MODE" >&2
    exit 2
    ;;
esac

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
  -e HOST_SLICER_LAUNCHER="$HOST_SLICER_LAUNCHER" \
  -e HOST_MRTRIX_BIN="$HOST_MRTRIX_BIN" \
  -e SMOKE_LFS_MODE="$SMOKE_LFS_MODE" \
  -e GIT_TERMINAL_PROMPT=0 \
  -e HOME=/work/home \
  -e XDG_CACHE_HOME=/work/home/.cache \
  -e XDG_CONFIG_HOME=/work/home/.config \
  -v "$HOST_SOFTWARE_ROOT:$HOST_SOFTWARE_ROOT:ro" \
  -v "$HOST_WORK_ROOT:/work" \
)
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
echo "[container] slicer=$HOST_SLICER_LAUNCHER"
echo "[container] mrtrix=$HOST_MRTRIX_BIN"
echo "[container] lfs_mode=$SMOKE_LFS_MODE"
test -x "$HOST_SLICER_LAUNCHER"
test -x "$HOST_MRTRIX_BIN/mrconvert"
GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none "$REPO_URL" /work/src/SlicerDDSurfer
cd /work/src/SlicerDDSurfer
git checkout "$REPO_REF"
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
'

echo "[rc-smoke] Logs: $HOST_WORK_ROOT/logs"
