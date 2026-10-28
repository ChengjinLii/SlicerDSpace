#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

SLICER_EXECUTABLE=${SLICER_EXECUTABLE:-/data/chengjin/software/Slicer-5.10.0-linux-amd64/Slicer}
PCRE2_DIR=${PCRE2_DIR:-/data/chengjin/software/libpcre2-16-0/usr/lib/x86_64-linux-gnu}
VIEWER_IMAGE=${VIEWER_IMAGE:-dmri-agent-slicer-dev:latest}
INSTALL_ROOT=${INSTALL_ROOT:-/tmp/slicerdds-extension-install-current}
HOME_STAGING=${HOME_STAGING:-/tmp/slicerdds-home-iso}
SELECT_SCRIPT=${SELECT_SCRIPT:-/tmp/slicerdsurfer_select_iso.py}
RUN_SCRIPT=${RUN_SCRIPT:-/tmp/run_slicerdds_iso_ext.sh}
CONTAINER_NAME=${CONTAINER_NAME:-slicerdsurfer-iso-viewer}
VNC_PORT=${VNC_PORT:-5903}
NOVNC_PORT=${NOVNC_PORT:-6083}
SLICER_VERSION=${SLICER_VERSION:-Slicer-5.10}
STARTUP_WAIT_SECONDS=${STARTUP_WAIT_SECONDS:-24}
POLL_INTERVAL_SECONDS=${POLL_INTERVAL_SECONDS:-2}
SOFTWARE_ROOTS=${SOFTWARE_ROOTS:-/data/chengjin/software}
HOST_TRACT_QUERIER_ROOT=${HOST_TRACT_QUERIER_ROOT:-${REPO_ROOT}/third_party/tract_querier}
HOST_WMA_ROOT=${HOST_WMA_ROOT:-${REPO_ROOT}/third_party/whitematteranalysis}
HOST_TRACTCLOUD_ROOT=${HOST_TRACTCLOUD_ROOT:-${REPO_ROOT}/third_party/TractCloud}

if [[ ! -x "${SLICER_EXECUTABLE}" ]]; then
  echo "Missing Slicer executable: ${SLICER_EXECUTABLE}" >&2
  exit 2
fi

if [[ ! -d "${PCRE2_DIR}" ]]; then
  echo "Missing PCRE2 library directory: ${PCRE2_DIR}" >&2
  exit 2
fi

python3 "${REPO_ROOT}/scripts/stage_slicer_extension.py" \
  --install-root "${INSTALL_ROOT}" \
  --slicer-version "${SLICER_VERSION}" \
  --clean \
  --link-mode copy >/tmp/slicerdds-stage.log

mkdir -p "${HOME_STAGING}"

cat > "${SELECT_SCRIPT}" <<'PY'
from pathlib import Path
import qt
import slicer

READY = Path("/tmp/slicerdsurfer_iso_ready.txt")
READY.unlink(missing_ok=True)
state = {"n": 0}


def open_module():
    state["n"] += 1
    try:
        mw = slicer.util.mainWindow()
        if mw:
            mw.move(0, 0)
            mw.resize(1800, 1100)
            mw.raise_()
            mw.activateWindow()
        mm = slicer.app.moduleManager()
        fm = mm.factoryManager() if mm else None
        names = set(fm.instantiatedModuleNames()) if fm else set()
        Path("/tmp/slicerdsurfer_iso_names.txt").write_text(
            "\n".join(sorted(names)),
            encoding="utf-8",
        )
        if "SlicerDSpace" in names:
            slicer.util.selectModule("SlicerDSpace")
            slicer.app.processEvents()
            READY.write_text("SLICERDSPACE_GUI_READY=1\n", encoding="utf-8")
            return
    except Exception as exc:
        Path("/tmp/slicerdsurfer_iso_error.txt").write_text(str(exc), encoding="utf-8")
    if state["n"] < 40:
        qt.QTimer.singleShot(1000, open_module)
    else:
        READY.write_text("SLICERDSPACE_GUI_TIMEOUT=1\n", encoding="utf-8")


qt.QTimer.singleShot(4000, open_module)
PY

cat > "${RUN_SCRIPT}" <<'SH'
set -euo pipefail
rm -f \
  /tmp/.X99-lock \
  /tmp/slicerdsurfer_iso.log \
  /tmp/slicerdsurfer_iso_ready.txt \
  /tmp/slicerdsurfer_iso_names.txt \
  /tmp/slicerdsurfer_iso_error.txt \
  /tmp/x11vnc.log \
  /tmp/websockify.log \
  /tmp/xvfb.log
Xvfb :99 -screen 0 1800x1100x24 -ac +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 &
sleep 2
export DISPLAY=:99
export HOME=/root
/usr/bin/x11vnc -display :99 -noshm -nopw -forever -shared -rfbport 5900 -o /tmp/x11vnc.log &
/usr/bin/websockify --web /usr/share/novnc 6080 127.0.0.1:5900 >/tmp/websockify.log 2>&1 &
LD_LIBRARY_PATH=/opt/pcre2 \
  /opt/Slicer-5.10.0-linux-amd64/Slicer \
  --no-splash \
  --disable-cli-modules \
  --additional-module-path /work/install/SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules \
  --python-script /work/select/slicerdsurfer_select_iso.py \
  >/tmp/slicerdsurfer_iso.log 2>&1 &
wait -n
SH

chmod +x "${SELECT_SCRIPT}" "${RUN_SCRIPT}"

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

DOCKER_MOUNTS=(
  -v "$(dirname "${SLICER_EXECUTABLE}"):/opt/Slicer-5.10.0-linux-amd64:ro"
  -v "${PCRE2_DIR}:/opt/pcre2:ro"
  -v "${INSTALL_ROOT}:/work/install:ro"
  -v "${HOME_STAGING}:/root:rw"
  -v "${SELECT_SCRIPT}:/work/select/slicerdsurfer_select_iso.py:ro"
  -v "${RUN_SCRIPT}:/run_slicerdds_iso_ext.sh:ro"
)
DOCKER_ENVS=()

IFS=':' read -r -a SOFTWARE_ROOT_ITEMS <<< "${SOFTWARE_ROOTS}"
for software_root in "${SOFTWARE_ROOT_ITEMS[@]}"; do
  software_root=${software_root/#\~/${HOME}}
  [[ -n "${software_root}" ]] || continue
  if [[ -d "${software_root}" ]]; then
    DOCKER_MOUNTS+=(-v "${software_root}:${software_root}:ro")
  fi
done

if [[ -d "${HOST_TRACT_QUERIER_ROOT}" ]]; then
  DOCKER_MOUNTS+=(-v "${HOST_TRACT_QUERIER_ROOT}:${HOST_TRACT_QUERIER_ROOT}:ro")
  DOCKER_ENVS+=(-e "SLICERDSPACE_TRACT_QUERIER_ROOT=${HOST_TRACT_QUERIER_ROOT}")
fi
if [[ -d "${HOST_WMA_ROOT}" ]]; then
  DOCKER_MOUNTS+=(-v "${HOST_WMA_ROOT}:${HOST_WMA_ROOT}:ro")
  DOCKER_ENVS+=(-e "SLICERDSPACE_WMA_ROOT=${HOST_WMA_ROOT}")
fi
if [[ -d "${HOST_TRACTCLOUD_ROOT}" ]]; then
  DOCKER_MOUNTS+=(-v "${HOST_TRACTCLOUD_ROOT}:${HOST_TRACTCLOUD_ROOT}:ro")
  DOCKER_ENVS+=(-e "SLICERDSPACE_TRACTCLOUD_ROOT=${HOST_TRACTCLOUD_ROOT}")
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${VNC_PORT}:5900" \
  -p "${NOVNC_PORT}:6080" \
  "${DOCKER_MOUNTS[@]}" \
  "${DOCKER_ENVS[@]}" \
  --entrypoint /bin/bash \
  "${VIEWER_IMAGE}" \
  /run_slicerdds_iso_ext.sh >/tmp/slicerdds-docker-run.log

deadline=$((SECONDS + STARTUP_WAIT_SECONDS))
READY_STATE=""
while (( SECONDS < deadline )); do
  if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    echo "Viewer container did not stay up: ${CONTAINER_NAME}" >&2
    docker logs "${CONTAINER_NAME}" 2>&1 || true
    exit 3
  fi
  READY_STATE=$(docker exec "${CONTAINER_NAME}" bash -lc 'cat /tmp/slicerdsurfer_iso_ready.txt 2>/dev/null || true')
  if [[ "${READY_STATE}" == "SLICERDSPACE_GUI_READY=1" ]]; then
    break
  fi
  sleep "${POLL_INTERVAL_SECONDS}"
done

if [[ "${READY_STATE}" != "SLICERDSPACE_GUI_READY=1" ]]; then
  echo "SlicerDSpace did not report ready. Current state: ${READY_STATE:-<empty>}" >&2
  docker exec "${CONTAINER_NAME}" bash -lc '
    echo ---error---;
    cat /tmp/slicerdsurfer_iso_error.txt 2>/dev/null || true;
    echo ---names---;
    grep -n "^SlicerDSpace$" /tmp/slicerdsurfer_iso_names.txt 2>/dev/null || true;
    echo ---tail---;
    tail -n 120 /tmp/slicerdsurfer_iso.log 2>/dev/null || true
  ' || true
  exit 4
fi

echo "SLICERDSPACE_GUI_READY=1"
echo "Container: ${CONTAINER_NAME}"
echo "Mounted software roots: ${SOFTWARE_ROOTS}"
if [[ -d "${HOST_TRACT_QUERIER_ROOT}" ]]; then
  echo "Mounted TractQuerier root: ${HOST_TRACT_QUERIER_ROOT}"
fi
echo "VNC: http://127.0.0.1:${NOVNC_PORT}/vnc.html?host=localhost&port=${NOVNC_PORT}&path=websockify&autoconnect=true&resize=scale"
