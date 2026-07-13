#!/usr/bin/env bash
set -euo pipefail

MINIFORGE_VERSION="26.3.2-3"
MINIFORGE_SHA256="848194851a98903134187fbb4ab50efe87b003e0c0f808f97644b7524a62bf2c"
MINIFORGE_URL="https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/Miniforge3-${MINIFORGE_VERSION}-Linux-x86_64.sh"
MRTRIX_VERSION="3.0.8"
FSL_EDDY_VERSION="2602.0"
FSL_EDDY_BUILD="hb35a746_0"
FSL_TOPUP_VERSION="2203.5"
FSL_TOPUP_BUILD="ha905fa9_6"
FSL_PUBLIC_CHANNEL="https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/public/"
FREESURFER_VERSION="7.4.1"
FREESURFER_URL="https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.4.1/freesurfer-linux-ubuntu22_amd64-7.4.1.tar.gz"
FREESURFER_MD5="4275a307a1a91043587f659389b3e9a8"

TRACT_QUERIER_REPOSITORY="https://github.com/demianw/tract_querier.git"
TRACT_QUERIER_COMMIT="5c69c594d489859e08485110678dca7f6f4cba40"
WMA_REPOSITORY="https://github.com/SlicerDMRI/whitematteranalysis.git"
WMA_COMMIT="4532b911386d2d1bc7ebba63fdd13e65b1660623"
TRACTCLOUD_REPOSITORY="https://github.com/SlicerDMRI/TractCloud.git"
TRACTCLOUD_COMMIT="94de6275d07d7b5eeb50e4cd4d6e85fde29d5fb0"

INSTALL_ROOT="${HOME}/.local/share/slicerdsurfer"
REPO_ROOT=""
DISTRO="Ubuntu"
FREESURFER_LICENSE=""
SLICER_WINDOWS_EXE=""
SKIP_LARGE_DOWNLOADS=0
SKIP_FREESURFER=0

ORG_REG_URL=""
ORG_REG_SHA256=""
ORG_800_URL=""
ORG_800_SHA256=""
TRACTCLOUD_TRAIN_URL=""
TRACTCLOUD_TRAIN_SHA256=""
TRACTCLOUD_MODEL_URL=""
TRACTCLOUD_MODEL_SHA256=""

usage() {
  cat <<'EOF'
Usage: install_runtime.sh --repo-root PATH [options]

This script is invoked by install_deps_windows.ps1 after apt packages have
been installed with `wsl.exe --user root`. It never invokes sudo.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT=$2; shift 2 ;;
    --repo-root) REPO_ROOT=$2; shift 2 ;;
    --distro) DISTRO=$2; shift 2 ;;
    --freesurfer-license) FREESURFER_LICENSE=$2; shift 2 ;;
    --slicer-windows-exe) SLICER_WINDOWS_EXE=$2; shift 2 ;;
    --org-reg-url) ORG_REG_URL=$2; shift 2 ;;
    --org-reg-sha256) ORG_REG_SHA256=$2; shift 2 ;;
    --org-800-url) ORG_800_URL=$2; shift 2 ;;
    --org-800-sha256) ORG_800_SHA256=$2; shift 2 ;;
    --tractcloud-train-url) TRACTCLOUD_TRAIN_URL=$2; shift 2 ;;
    --tractcloud-train-sha256) TRACTCLOUD_TRAIN_SHA256=$2; shift 2 ;;
    --tractcloud-model-url) TRACTCLOUD_MODEL_URL=$2; shift 2 ;;
    --tractcloud-model-sha256) TRACTCLOUD_MODEL_SHA256=$2; shift 2 ;;
    --skip-large-downloads) SKIP_LARGE_DOWNLOADS=1; shift ;;
    --skip-freesurfer) SKIP_FREESURFER=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$REPO_ROOT" || ! -f "$REPO_ROOT/scripts/wsl/requirements-runtime.txt" ]]; then
  echo "--repo-root must identify the SlicerDDSurfer checkout" >&2
  exit 2
fi
if [[ $EUID -eq 0 ]]; then
  echo "Run install_runtime.sh as the distribution's normal user, not root." >&2
  exit 2
fi
if [[ "$INSTALL_ROOT" == "~/"* ]]; then
  INSTALL_ROOT="${HOME}/${INSTALL_ROOT#~/}"
fi
if [[ "$INSTALL_ROOT" != /* ]]; then
  echo "--install-root must be an absolute Linux path (or begin with ~/)." >&2
  exit 2
fi

for digest in "$ORG_REG_SHA256" "$ORG_800_SHA256" "$TRACTCLOUD_TRAIN_SHA256" "$TRACTCLOUD_MODEL_SHA256"; do
  if [[ ! "$digest" =~ ^[0-9a-fA-F]{64}$ ]]; then
    echo "Every external atlas/model resource requires an explicit 64-character SHA-256." >&2
    exit 2
  fi
done

DOWNLOAD_ROOT="$INSTALL_ROOT/downloads"
THIRD_PARTY_ROOT="$INSTALL_ROOT/third_party"
DATA_ROOT="$INSTALL_ROOT/data"
BIN_ROOT="$INSTALL_ROOT/bin"
STATE_ROOT="$INSTALL_ROOT/state"
MINIFORGE_ROOT="$INSTALL_ROOT/miniforge3"
RUNTIME_ENV="$INSTALL_ROOT/envs/runtime"
FSL_ENV="$INSTALL_ROOT/envs/fsl-${FSL_EDDY_VERSION}"
FREESURFER_HOME="$INSTALL_ROOT/opt/freesurfer-${FREESURFER_VERSION}"
ORG_ATLAS_ROOT="$DATA_ROOT/ORG-Atlases"
TRACTCLOUD_DATA_ROOT="$DATA_ROOT/tractcloud"
TRACT_QUERIER_ROOT="$THIRD_PARTY_ROOT/tract_querier"
WMA_ROOT="$THIRD_PARTY_ROOT/whitematteranalysis"
TRACTCLOUD_ROOT="$THIRD_PARTY_ROOT/TractCloud"

mkdir -p "$DOWNLOAD_ROOT" "$THIRD_PARTY_ROOT" "$DATA_ROOT" "$BIN_ROOT" "$STATE_ROOT" "$INSTALL_ROOT/opt" "$INSTALL_ROOT/envs"

sha256_of() {
  sha256sum "$1" | awk '{print tolower($1)}'
}

md5_of() {
  md5sum "$1" | awk '{print tolower($1)}'
}

download_sha256() {
  local url=$1
  local expected=${2,,}
  local destination=$3
  if [[ -f "$destination" ]] && [[ "$(sha256_of "$destination")" == "$expected" ]]; then
    echo "[download] verified cache: $destination"
    return
  fi
  echo "[download] $url"
  curl --fail --location --retry 5 --retry-all-errors --continue-at - --output "${destination}.part" "$url"
  local actual
  actual=$(sha256_of "${destination}.part")
  if [[ "$actual" != "$expected" ]]; then
    rm -f "${destination}.part"
    echo "SHA-256 mismatch for $url: expected $expected, got $actual" >&2
    exit 3
  fi
  mv "${destination}.part" "$destination"
}

download_md5() {
  local url=$1
  local expected=${2,,}
  local destination=$3
  if [[ -f "$destination" ]] && [[ "$(md5_of "$destination")" == "$expected" ]]; then
    echo "[download] verified cache: $destination"
    return
  fi
  echo "[download] $url"
  curl --fail --location --retry 5 --retry-all-errors --continue-at - --output "${destination}.part" "$url"
  local actual
  actual=$(md5_of "${destination}.part")
  if [[ "$actual" != "$expected" ]]; then
    rm -f "${destination}.part"
    echo "MD5 mismatch for $url: expected $expected, got $actual" >&2
    exit 3
  fi
  mv "${destination}.part" "$destination"
}

retry_command() {
  local attempt=1
  local maximum=5
  while true; do
    if "$@"; then
      return 0
    fi
    if [[ $attempt -ge $maximum ]]; then
      echo "Command failed after $maximum attempts: $*" >&2
      return 1
    fi
    echo "[retry] attempt $attempt/$maximum failed; retrying in $((attempt * 3)) seconds: $*" >&2
    sleep $((attempt * 3))
    attempt=$((attempt + 1))
  done
}

clone_with_retry() {
  local repository=$1
  local destination=$2
  local attempt
  for attempt in 1 2 3 4 5; do
    rm -rf "$destination"
    if git clone --filter=blob:none --no-checkout "$repository" "$destination"; then
      return 0
    fi
    if [[ $attempt -lt 5 ]]; then
      echo "[retry] Git clone attempt $attempt/5 failed; retrying in $((attempt * 3)) seconds." >&2
      sleep $((attempt * 3))
    fi
  done
  echo "Git clone failed after 5 attempts: $repository" >&2
  return 1
}

clone_pinned() {
  local repository=$1
  local commit=$2
  local destination=$3
  if [[ -e "$destination" && ! -d "$destination/.git" ]]; then
    echo "Refusing to replace non-Git path: $destination" >&2
    exit 4
  fi
  if [[ ! -d "$destination/.git" ]]; then
    local temporary_clone="${destination}.clone.$$"
    rm -rf "$temporary_clone"
    clone_with_retry "$repository" "$temporary_clone"
    mv "$temporary_clone" "$destination"
  fi
  local configured_remote
  configured_remote=$(git -C "$destination" remote get-url origin)
  if [[ "$configured_remote" != "$repository" ]]; then
    echo "Repository remote mismatch at $destination: $configured_remote" >&2
    exit 4
  fi
  if ! git -C "$destination" cat-file -e "${commit}^{commit}" 2>/dev/null; then
    retry_command git -C "$destination" fetch --depth 1 origin "$commit"
  fi
  git -C "$destination" checkout --detach --force "$commit"
  local actual
  actual=$(git -C "$destination" rev-parse HEAD)
  if [[ "$actual" != "$commit" ]]; then
    echo "Pinned checkout verification failed at $destination" >&2
    exit 4
  fi
}

replace_directory_from_zip() {
  local archive=$1
  local expected_name=$2
  local destination=$3
  local temporary="$INSTALL_ROOT/tmp/${expected_name}.$$"
  mkdir -p "$temporary"
  unzip -q "$archive" -d "$temporary"
  local source
  source=$(find "$temporary" -type d -name "$expected_name" ! -path '*/__MACOSX/*' -print -quit)
  if [[ -z "$source" ]]; then
    echo "Archive $archive does not contain $expected_name" >&2
    exit 5
  fi
  case "$destination" in
    "$DATA_ROOT"/*) ;;
    *) echo "Unsafe data destination: $destination" >&2; exit 5 ;;
  esac
  rm -rf "$destination"
  mkdir -p "$(dirname "$destination")"
  mv "$source" "$destination"
  rm -rf "$temporary"
}

replace_directory_from_tar() {
  local archive=$1
  local expected_name=$2
  local destination=$3
  local temporary="$INSTALL_ROOT/tmp/${expected_name}.$$"
  mkdir -p "$temporary"
  tar -xzf "$archive" -C "$temporary"
  local source
  source=$(find "$temporary" -type d -name "$expected_name" -print -quit)
  if [[ -z "$source" ]]; then
    echo "Archive $archive does not contain $expected_name" >&2
    exit 5
  fi
  case "$destination" in
    "$DATA_ROOT"/*) ;;
    *) echo "Unsafe data destination: $destination" >&2; exit 5 ;;
  esac
  rm -rf "$destination"
  mkdir -p "$(dirname "$destination")"
  mv "$source" "$destination"
  rm -rf "$temporary"
}

echo "[1/8] Installing pinned Miniforge ${MINIFORGE_VERSION}"
MINIFORGE_MARKER="$MINIFORGE_ROOT/.slicerdsurfer-miniforge-version"
if [[ -x "$MINIFORGE_ROOT/bin/conda" ]]; then
  if [[ ! -f "$MINIFORGE_MARKER" ]] || [[ "$(cat "$MINIFORGE_MARKER")" != "$MINIFORGE_VERSION" ]]; then
    echo "Existing unverified Miniforge root: $MINIFORGE_ROOT. Use a different --install-root." >&2
    exit 6
  fi
else
  miniforge_installer="$DOWNLOAD_ROOT/Miniforge3-${MINIFORGE_VERSION}-Linux-x86_64.sh"
  download_sha256 "$MINIFORGE_URL" "$MINIFORGE_SHA256" "$miniforge_installer"
  bash "$miniforge_installer" -b -p "$MINIFORGE_ROOT"
  printf '%s\n' "$MINIFORGE_VERSION" > "$MINIFORGE_MARKER"
fi
CONDA="$MINIFORGE_ROOT/bin/conda"

echo "[2/8] Creating/updating runtime environment (MRtrix3 ${MRTRIX_VERSION})"
if [[ ! -x "$RUNTIME_ENV/bin/python" ]]; then
  "$CONDA" create -y -p "$RUNTIME_ENV" -c mrtrix3 -c conda-forge "python=3.10" "mrtrix3=${MRTRIX_VERSION}" pip
else
  "$CONDA" install -y -p "$RUNTIME_ENV" -c mrtrix3 -c conda-forge "python=3.10" "mrtrix3=${MRTRIX_VERSION}" pip
fi
"$RUNTIME_ENV/bin/python" -m pip install --upgrade "pip==25.3"
"$RUNTIME_ENV/bin/python" -m pip install -r "$REPO_ROOT/scripts/wsl/requirements-runtime.txt"
if ! "$RUNTIME_ENV/bin/mrconvert" -version 2>&1 | grep -q "${MRTRIX_VERSION}"; then
  echo "MRtrix3 version verification failed" >&2
  exit 6
fi

echo "[3/8] Creating/updating isolated FSL environment"
fsl_packages=(
  "fsl-eddy=${FSL_EDDY_VERSION}=${FSL_EDDY_BUILD}"
  "fsl-topup=${FSL_TOPUP_VERSION}=${FSL_TOPUP_BUILD}"
)
if [[ ! -x "$FSL_ENV/bin/eddy" ]]; then
  "$CONDA" create -y --override-channels --strict-channel-priority \
    -p "$FSL_ENV" -c "$FSL_PUBLIC_CHANNEL" -c conda-forge "${fsl_packages[@]}"
else
  "$CONDA" install -y --override-channels --strict-channel-priority \
    -p "$FSL_ENV" -c "$FSL_PUBLIC_CHANNEL" -c conda-forge "${fsl_packages[@]}"
fi
verify_conda_package() {
  local package_name=$1
  local expected_version=$2
  local expected_build=$3
  "$CONDA" list -p "$FSL_ENV" --json | "$RUNTIME_ENV/bin/python" -c '
import json
import sys

name, version, build = sys.argv[1:]
records = [record for record in json.load(sys.stdin) if record.get("name") == name]
if not any(record.get("version") == version and record.get("build_string") == build for record in records):
    raise SystemExit(f"Pinned package verification failed: {name}={version}={build}; found {records}")
' "$package_name" "$expected_version" "$expected_build"
}
verify_conda_package "fsl-eddy" "$FSL_EDDY_VERSION" "$FSL_EDDY_BUILD"
verify_conda_package "fsl-topup" "$FSL_TOPUP_VERSION" "$FSL_TOPUP_BUILD"
for command in eddy eddy_cpu topup; do
  if [[ ! -x "$FSL_ENV/bin/$command" ]]; then
    echo "FSL command verification failed: $FSL_ENV/bin/$command" >&2
    exit 6
  fi
done

echo "[4/8] Checking out pinned bundle backends"
clone_pinned "$TRACT_QUERIER_REPOSITORY" "$TRACT_QUERIER_COMMIT" "$TRACT_QUERIER_ROOT"
clone_pinned "$WMA_REPOSITORY" "$WMA_COMMIT" "$WMA_ROOT"
clone_pinned "$TRACTCLOUD_REPOSITORY" "$TRACTCLOUD_COMMIT" "$TRACTCLOUD_ROOT"
"$RUNTIME_ENV/bin/python" -m pip install --no-build-isolation --no-deps \
  -e "$TRACT_QUERIER_ROOT" -e "$WMA_ROOT" -e "$TRACTCLOUD_ROOT"

echo "[5/8] Installing verified TractCloud data"
tractcloud_train_archive="$DOWNLOAD_ROOT/TrainData_800clu800ol.tar.gz"
tractcloud_model_archive="$DOWNLOAD_ROOT/TrainedModel.tar.gz"
download_sha256 "$TRACTCLOUD_TRAIN_URL" "$TRACTCLOUD_TRAIN_SHA256" "$tractcloud_train_archive"
download_sha256 "$TRACTCLOUD_MODEL_URL" "$TRACTCLOUD_MODEL_SHA256" "$tractcloud_model_archive"
if [[ ! -d "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol" ]] ||
   [[ ! -f "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol/.slicerdsurfer-source-sha256" ]] ||
   [[ "$(cat "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol/.slicerdsurfer-source-sha256" 2>/dev/null || true)" != "${TRACTCLOUD_TRAIN_SHA256,,}" ]]; then
  replace_directory_from_tar "$tractcloud_train_archive" "TrainData_800clu800ol" "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol"
  printf '%s\n' "${TRACTCLOUD_TRAIN_SHA256,,}" > "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol/.slicerdsurfer-source-sha256"
fi
if [[ ! -d "$TRACTCLOUD_DATA_ROOT/TrainedModel" ]] ||
   [[ ! -f "$TRACTCLOUD_DATA_ROOT/TrainedModel/.slicerdsurfer-source-sha256" ]] ||
   [[ "$(cat "$TRACTCLOUD_DATA_ROOT/TrainedModel/.slicerdsurfer-source-sha256" 2>/dev/null || true)" != "${TRACTCLOUD_MODEL_SHA256,,}" ]]; then
  replace_directory_from_tar "$tractcloud_model_archive" "TrainedModel" "$TRACTCLOUD_DATA_ROOT/TrainedModel"
  printf '%s\n' "${TRACTCLOUD_MODEL_SHA256,,}" > "$TRACTCLOUD_DATA_ROOT/TrainedModel/.slicerdsurfer-source-sha256"
fi

echo "[6/8] Installing verified ORG atlas resources"
if [[ $SKIP_LARGE_DOWNLOADS -eq 0 ]]; then
  org_reg_archive="$DOWNLOAD_ROOT/ORG-RegAtlas-100HCP.zip"
  org_800_archive="$DOWNLOAD_ROOT/ORG-800FC-100HCP.zip"
  download_sha256 "$ORG_REG_URL" "$ORG_REG_SHA256" "$org_reg_archive"
  download_sha256 "$ORG_800_URL" "$ORG_800_SHA256" "$org_800_archive"
  if [[ ! -d "$ORG_ATLAS_ROOT/ORG-RegAtlas-100HCP" ]] ||
     [[ "$(cat "$ORG_ATLAS_ROOT/ORG-RegAtlas-100HCP/.slicerdsurfer-source-sha256" 2>/dev/null || true)" != "${ORG_REG_SHA256,,}" ]]; then
    replace_directory_from_zip "$org_reg_archive" "ORG-RegAtlas-100HCP" "$ORG_ATLAS_ROOT/ORG-RegAtlas-100HCP"
    printf '%s\n' "${ORG_REG_SHA256,,}" > "$ORG_ATLAS_ROOT/ORG-RegAtlas-100HCP/.slicerdsurfer-source-sha256"
  fi
  if [[ ! -d "$ORG_ATLAS_ROOT/ORG-800FC-100HCP" ]] ||
     [[ "$(cat "$ORG_ATLAS_ROOT/ORG-800FC-100HCP/.slicerdsurfer-source-sha256" 2>/dev/null || true)" != "${ORG_800_SHA256,,}" ]]; then
    replace_directory_from_zip "$org_800_archive" "ORG-800FC-100HCP" "$ORG_ATLAS_ROOT/ORG-800FC-100HCP"
    printf '%s\n' "${ORG_800_SHA256,,}" > "$ORG_ATLAS_ROOT/ORG-800FC-100HCP/.slicerdsurfer-source-sha256"
  fi
else
  echo "[skip] ORG archives are large; preserving any existing verified atlas."
fi

echo "[7/8] Installing FreeSurfer ${FREESURFER_VERSION}"
if [[ $SKIP_FREESURFER -eq 0 ]]; then
  if [[ -x "$FREESURFER_HOME/bin/recon-all" ]] &&
     [[ "$(cat "$FREESURFER_HOME/.slicerdsurfer-version" 2>/dev/null || true)" != "$FREESURFER_VERSION" ]]; then
    echo "Existing FreeSurfer root has no matching SlicerDDSurfer version marker: $FREESURFER_HOME" >&2
    exit 7
  fi
  if [[ ! -x "$FREESURFER_HOME/bin/recon-all" ]]; then
    if [[ $SKIP_LARGE_DOWNLOADS -eq 1 ]]; then
      echo "[skip] FreeSurfer archive is approximately 9 GB."
    else
      freesurfer_archive="$DOWNLOAD_ROOT/freesurfer-linux-ubuntu22_amd64-${FREESURFER_VERSION}.tar.gz"
      download_md5 "$FREESURFER_URL" "$FREESURFER_MD5" "$freesurfer_archive"
      temporary="$INSTALL_ROOT/tmp/freesurfer.$$"
      mkdir -p "$temporary"
      tar -xzf "$freesurfer_archive" -C "$temporary"
      if [[ ! -d "$temporary/freesurfer" ]]; then
        echo "FreeSurfer archive layout is not recognized" >&2
        exit 7
      fi
      rm -rf "$FREESURFER_HOME"
      mv "$temporary/freesurfer" "$FREESURFER_HOME"
      rm -rf "$temporary"
      printf '%s\n' "$FREESURFER_VERSION" > "$FREESURFER_HOME/.slicerdsurfer-version"
    fi
  fi
  if [[ -x "$FREESURFER_HOME/bin/recon-all" ]]; then
    if [[ -z "$FREESURFER_LICENSE" || ! -f "$FREESURFER_LICENSE" ]]; then
      echo "A valid --freesurfer-license file is required for the installed FreeSurfer runtime." >&2
      exit 7
    fi
    cp "$FREESURFER_LICENSE" "$FREESURFER_HOME/license.txt"
    chmod 600 "$FREESURFER_HOME/license.txt"
  fi
fi

echo "[8/8] Creating the Windows Slicer reverse bridge and state file"
RUNTIME_COMMAND_BRIDGE="$BIN_ROOT/run-in-runtime"
printf '#!/usr/bin/env bash\nexport FSLDIR=%q\nexport FSLOUTPUTTYPE=NIFTI_GZ\nexport PATH=%q:%q:%q/bin:%q/utilities:%q:$PATH\nexport PYTHONPATH=%q${PYTHONPATH:+:$PYTHONPATH}\nexec "$@"\n' \
  "$FSL_ENV" "$RUNTIME_ENV/bin" "$FSL_ENV/bin" "$WMA_ROOT" "$WMA_ROOT" "$BIN_ROOT" "$WMA_ROOT" > "$RUNTIME_COMMAND_BRIDGE"
chmod +x "$RUNTIME_COMMAND_BRIDGE"
SLICER_BRIDGE=""
if [[ -n "$SLICER_WINDOWS_EXE" ]]; then
  SLICER_BRIDGE="$BIN_ROOT/Slicer"
  printf '#!/usr/bin/env bash\nexec /bin/bash %q %q "$@"\n' \
    "$REPO_ROOT/scripts/wsl/slicer_windows_bridge.sh" "$SLICER_WINDOWS_EXE" > "$SLICER_BRIDGE"
  chmod +x "$SLICER_BRIDGE"
fi

ORG_READY=0
if [[ -d "$ORG_ATLAS_ROOT/ORG-RegAtlas-100HCP" &&
      -d "$ORG_ATLAS_ROOT/ORG-800FC-100HCP" &&
      "$(cat "$ORG_ATLAS_ROOT/ORG-RegAtlas-100HCP/.slicerdsurfer-source-sha256" 2>/dev/null || true)" == "${ORG_REG_SHA256,,}" &&
      "$(cat "$ORG_ATLAS_ROOT/ORG-800FC-100HCP/.slicerdsurfer-source-sha256" 2>/dev/null || true)" == "${ORG_800_SHA256,,}" ]]; then
  ORG_READY=1
fi
TRACTCLOUD_READY=0
if [[ -f "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol/HCP_mass_center.npy" &&
      -f "$TRACTCLOUD_DATA_ROOT/TrainedModel/best_tract_f1_model.pth" &&
      "$(cat "$TRACTCLOUD_DATA_ROOT/TrainData_800clu800ol/.slicerdsurfer-source-sha256" 2>/dev/null || true)" == "${TRACTCLOUD_TRAIN_SHA256,,}" &&
      "$(cat "$TRACTCLOUD_DATA_ROOT/TrainedModel/.slicerdsurfer-source-sha256" 2>/dev/null || true)" == "${TRACTCLOUD_MODEL_SHA256,,}" ]]; then
  TRACTCLOUD_READY=1
fi
FREESURFER_READY=0
if [[ -x "$FREESURFER_HOME/bin/recon-all" &&
      -f "$FREESURFER_HOME/license.txt" &&
      "$(cat "$FREESURFER_HOME/.slicerdsurfer-version" 2>/dev/null || true)" == "$FREESURFER_VERSION" ]]; then
  FREESURFER_READY=1
fi
FSL_READY=0
if [[ -x "$FSL_ENV/bin/eddy" && -x "$FSL_ENV/bin/eddy_cpu" && -x "$FSL_ENV/bin/topup" ]]; then
  FSL_READY=1
fi

STATE_FILE="$STATE_ROOT/install-state.json"
export STATE_FILE DISTRO INSTALL_ROOT RUNTIME_ENV FSL_ENV FREESURFER_HOME ORG_ATLAS_ROOT TRACTCLOUD_DATA_ROOT
export TRACT_QUERIER_ROOT WMA_ROOT TRACTCLOUD_ROOT SLICER_BRIDGE ORG_READY TRACTCLOUD_READY FREESURFER_READY FSL_READY
export RUNTIME_COMMAND_BRIDGE
export MRTRIX_VERSION FSL_EDDY_VERSION FSL_EDDY_BUILD FSL_TOPUP_VERSION FSL_TOPUP_BUILD
export FREESURFER_VERSION TRACT_QUERIER_COMMIT WMA_COMMIT TRACTCLOUD_COMMIT MINIFORGE_VERSION
"$RUNTIME_ENV/bin/python" - <<'PY'
import json
import os
from pathlib import Path

def ready(name: str) -> bool:
    return os.environ[name] == "1"

payload = {
    "kind": "slicerdsurfer_windows_wsl_install_state",
    "version": 1,
    "distribution": os.environ["DISTRO"],
    "install_root": os.environ["INSTALL_ROOT"],
    "miniforge": {
        "version": os.environ["MINIFORGE_VERSION"],
        "root": str(Path(os.environ["INSTALL_ROOT"]) / "miniforge3"),
    },
    "runtime_env": os.environ["RUNTIME_ENV"],
    "mrtrix": {
        "version": os.environ["MRTRIX_VERSION"],
        "bin_dir": str(Path(os.environ["RUNTIME_ENV"]) / "bin"),
    },
    "fsl": {
        "eddy_version": os.environ["FSL_EDDY_VERSION"],
        "eddy_build": os.environ["FSL_EDDY_BUILD"],
        "topup_version": os.environ["FSL_TOPUP_VERSION"],
        "topup_build": os.environ["FSL_TOPUP_BUILD"],
        "home": os.environ["FSL_ENV"],
        "bin_dir": str(Path(os.environ["FSL_ENV"]) / "bin"),
        "ready": ready("FSL_READY"),
    },
    "freesurfer": {
        "version": os.environ["FREESURFER_VERSION"],
        "home": os.environ["FREESURFER_HOME"] if ready("FREESURFER_READY") else None,
        "ready": ready("FREESURFER_READY"),
    },
    "tract_querier": {
        "root": os.environ["TRACT_QUERIER_ROOT"],
        "commit": os.environ["TRACT_QUERIER_COMMIT"],
    },
    "wma": {
        "root": os.environ["WMA_ROOT"],
        "commit": os.environ["WMA_COMMIT"],
        "atlas_dir": os.environ["ORG_ATLAS_ROOT"] if ready("ORG_READY") else None,
        "atlas_ready": ready("ORG_READY"),
    },
    "tractcloud": {
        "root": os.environ["TRACTCLOUD_ROOT"],
        "commit": os.environ["TRACTCLOUD_COMMIT"],
        "python": str(Path(os.environ["RUNTIME_ENV"]) / "bin" / "python"),
        "data_dir": os.environ["TRACTCLOUD_DATA_ROOT"] if ready("TRACTCLOUD_READY") else None,
        "data_ready": ready("TRACTCLOUD_READY"),
    },
    "slicer_bridge": os.environ["SLICER_BRIDGE"] or None,
    "runtime_command_bridge": os.environ["RUNTIME_COMMAND_BRIDGE"],
}
state_file = Path(os.environ["STATE_FILE"])
state_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"SLICERDDSURFER_STATE_FILE={state_file}")
PY
