PYTHON ?= python3
export PYTHONPYCACHEPREFIX ?= $(CURDIR)/ignore/cache/pycache
SLICERDSPACE_RELEASE_ARGS ?=
SLICERDSPACE_TEST_PATTERN ?= test_*.py
SLICERDSPACE_SMOKE_SCRIPT ?= Testing/Python/slicer_extension_install_smoke.py

.PHONY: help test-fast test-slicer fresh-clone-smoke release-check release-plan release-artifacts prepare-inputs output-tree-report subject-report protocol-benchmarks install-plan clean-local lint

help:
	@echo "SlicerDSpace developer targets:"
	@echo "  make test-fast      Run repository Python unit tests without launching Slicer."
	@echo "  make test-slicer    Run Slicer smoke tests with xvfb-run or an existing DISPLAY/VNC session."
	@echo "  make fresh-clone-smoke Run a CI-safe fresh-clone smoke test without downloading large assets."
	@echo "  make release-check  Run release audit, model asset verification, and release validation."
	@echo "  make release-plan   Run release validation only. Requires SLICERDSPACE_RELEASE_SUBJECT_ROOT."
	@echo "  make release-artifacts Build lockfile and code-only archive metadata."
	@echo "  make prepare-inputs Normalize DICOM/NIfTI/NRRD inputs into a subject-root."
	@echo "  make output-tree-report Generate annotated HTML for the release output tree."
	@echo "  make subject-report Generate subject-level HTML/JSON/Markdown reports from a run manifest."
	@echo "  make protocol-benchmarks Generate benchmark CSV/JSON and publication-oriented figures."
	@echo "  make install-plan   Write a dependency plan without mutating the system."
	@echo "  make clean-local    Remove caches only; preserve reports and release evidence."
	@echo "  make lint           Run ruff if installed."

test-fast:
	$(PYTHON) -m unittest discover -s Testing/Python -p "$(SLICERDSPACE_TEST_PATTERN)"

fresh-clone-smoke:
	SMOKE_ASSET_MODE="$${SMOKE_ASSET_MODE:-plan}" \
	SMOKE_REPO_URL="$${SMOKE_REPO_URL:-$$(pwd)}" \
	SMOKE_REF="$${SMOKE_REF:-$$(git rev-parse HEAD)}" \
	SMOKE_ROOT="$${SMOKE_ROOT:-/tmp/slicerdsurfer-fresh-clone-smoke}" \
	bash scripts/smoke_fresh_clone.sh

.PHONY: test-slicer-coordinates
test-slicer-coordinates:
	$(MAKE) test-slicer SLICERDSPACE_SMOKE_SCRIPT=Testing/Python/slicer_surface_coordinate_smoke.py

test-slicer:
	: "$${SLICERDSPACE_SLICER_LAUNCHER:?Set SLICERDSPACE_SLICER_LAUNCHER to the Slicer launcher}"
	$(PYTHON) scripts/stage_slicer_extension.py --install-root "$${SLICERDSPACE_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}" --clean --link-mode copy
	if [ -n "$${SLICERDSPACE_XVFB_RUN:-}" ] && [ "$${SLICERDSPACE_XVFB_RUN}" != "none" ]; then \
	  env PATH="$$(dirname "$${SLICERDSPACE_XVFB_RUN}"):$${PATH}" \
	    SLICERDSPACE_DISABLE_FIRST_RUN_WIZARD="$${SLICERDSPACE_DISABLE_FIRST_RUN_WIZARD:-1}" \
	    SLICERDSPACE_USER_CONFIG="$${SLICERDSPACE_USER_CONFIG:-/tmp/slicerdsurfer-test-user-config.json}" \
	    SLICERDSPACE_EXTENSION_MODULE_DIR="$${SLICERDSPACE_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules" \
	    "$${SLICERDSPACE_XVFB_RUN}" -a "$${SLICERDSPACE_SLICER_LAUNCHER}" --no-splash --disable-cli-modules \
	    --additional-module-paths "$${SLICERDSPACE_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules" \
	    --python-script "$(SLICERDSPACE_SMOKE_SCRIPT)"; \
	elif [ "$${SLICERDSPACE_USE_EXISTING_DISPLAY:-0}" = "1" ] || [ -n "$${DISPLAY:-}" ] || [ -n "$${WAYLAND_DISPLAY:-}" ]; then \
	  env SLICERDSPACE_EXTENSION_MODULE_DIR="$${SLICERDSPACE_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules" \
	    SLICERDSPACE_DISABLE_FIRST_RUN_WIZARD="$${SLICERDSPACE_DISABLE_FIRST_RUN_WIZARD:-1}" \
	    SLICERDSPACE_USER_CONFIG="$${SLICERDSPACE_USER_CONFIG:-/tmp/slicerdsurfer-test-user-config.json}" \
	    "$${SLICERDSPACE_SLICER_LAUNCHER}" --no-splash --disable-cli-modules \
	    --additional-module-paths "$${SLICERDSPACE_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules" \
	    --python-script "$(SLICERDSPACE_SMOKE_SCRIPT)"; \
	else \
	  echo "Set SLICERDSPACE_XVFB_RUN=/path/to/xvfb-run, or run inside an existing X/VNC session with SLICERDSPACE_USE_EXISTING_DISPLAY=1."; \
	  exit 2; \
	fi

release-plan:
	: "$${SLICERDSPACE_RELEASE_SUBJECT_ROOT:?Set SLICERDSPACE_RELEASE_SUBJECT_ROOT to a subject-root fixture}"
	$(PYTHON) scripts/release_validation.py --subject-root "$${SLICERDSPACE_RELEASE_SUBJECT_ROOT}" $(SLICERDSPACE_RELEASE_ARGS)

release-check:
	$(PYTHON) scripts/release_audit.py
	$(PYTHON) scripts/download_model_assets.py --profile core --verify-only
	$(MAKE) release-plan

release-artifacts:
	$(PYTHON) scripts/build_release_artifacts.py \
	  --release-validation-report "$${SLICERDSPACE_RELEASE_VALIDATION_REPORT:-/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/release_validation/release_validation_report.json}"

prepare-inputs:
	: "$${SLICERDSPACE_SOURCE:?Set SLICERDSPACE_SOURCE to DICOM, NIfTI, NRRD/NHDR, or a canonical subject root}"
	: "$${SLICERDSPACE_SUBJECT_ROOT:?Set SLICERDSPACE_SUBJECT_ROOT to the destination subject root}"
	: "$${SLICERDSPACE_SUBJECT_ID:?Set SLICERDSPACE_SUBJECT_ID}"
	$(PYTHON) scripts/prepare_inputs.py \
	  --source "$${SLICERDSPACE_SOURCE}" \
	  --subject-root "$${SLICERDSPACE_SUBJECT_ROOT}" \
	  --subject-id "$${SLICERDSPACE_SUBJECT_ID}" \
	  $${SLICERDSPACE_SOURCE_KIND:+--source-kind "$${SLICERDSPACE_SOURCE_KIND}"} \
	  $${SLICERDSPACE_BVAL:+--bval "$${SLICERDSPACE_BVAL}"} \
	  $${SLICERDSPACE_BVEC:+--bvec "$${SLICERDSPACE_BVEC}"} \
	  $${SLICERDSPACE_MASK:+--mask "$${SLICERDSPACE_MASK}"} \
	  $${SLICERDSPACE_FORCE:+--force}

output-tree-report:
	$(PYTHON) Testing/Python/generate_output_tree_report.py \
	  --output-root "$${SLICERDSPACE_OUTPUT_ROOT:-/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs}" \
	  --dest "$${SLICERDSPACE_OUTPUT_TREE_HTML:-ignore/local_reports/SlicerDSpace_100307_release_candidate_output_tree.html}"

subject-report:
	: "$${SLICERDSPACE_SUBJECT_ROOT:?Set SLICERDSPACE_SUBJECT_ROOT to a subject root}"
	$(PYTHON) scripts/generate_subject_report.py \
	  --subject-root "$${SLICERDSPACE_SUBJECT_ROOT}" \
	  $${SLICERDSPACE_OUTPUT_ROOT:+--output-root "$${SLICERDSPACE_OUTPUT_ROOT}"} \
	  --run-name "$${SLICERDSPACE_RUN_NAME:-Test1}"

protocol-benchmarks:
	: "$${SLICERDSPACE_BENCHMARK_INPUT:?Set SLICERDSPACE_BENCHMARK_INPUT to an output tree or orchestration manifest}"
	$(PYTHON) scripts/generate_protocol_benchmarks.py \
	  --input "$${SLICERDSPACE_BENCHMARK_INPUT}" \
	  --output-dir "$${SLICERDSPACE_BENCHMARK_OUTPUT:-ignore/protocol_benchmarks}"

install-plan:
	$(PYTHON) scripts/install_dependencies.py --all --output-dir "$${SLICERDSPACE_INSTALL_PLAN_DIR:-ignore/local_reports/install_plan}" --platform "$${SLICERDSPACE_PLATFORM:-$$(uname -s)}"

clean-local:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache .ruff_cache .mypy_cache ignore/cache

lint:
	$(PYTHON) -m ruff check .
