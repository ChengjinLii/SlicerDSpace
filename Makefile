PYTHON ?= python3
SLICERDDSURFER_RELEASE_ARGS ?=
SLICERDDSURFER_TEST_PATTERN ?= test_*.py

.PHONY: help test-fast test-slicer release-check release-plan release-artifacts output-tree-report lint

help:
	@echo "SlicerDDSurfer developer targets:"
	@echo "  make test-fast      Run repository Python unit tests without launching Slicer."
	@echo "  make test-slicer    Run Slicer smoke tests with xvfb-run or an existing DISPLAY/VNC session."
	@echo "  make release-check  Run release audit, model asset verification, and release validation."
	@echo "  make release-plan   Run release validation only. Requires SLICERDDSURFER_RELEASE_SUBJECT_ROOT."
	@echo "  make release-artifacts Build lockfile and code-only archive metadata."
	@echo "  make output-tree-report Generate annotated HTML for the release output tree."
	@echo "  make lint           Run ruff if installed."

test-fast:
	$(PYTHON) -m unittest discover -s Testing/Python -p "$(SLICERDDSURFER_TEST_PATTERN)"

test-slicer:
	: "$${SLICERDDSURFER_SLICER_LAUNCHER:?Set SLICERDDSURFER_SLICER_LAUNCHER to the Slicer launcher}"
	$(PYTHON) scripts/stage_slicer_extension.py --install-root "$${SLICERDDSURFER_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}" --clean --link-mode copy
	if [ -n "$${SLICERDDSURFER_XVFB_RUN:-}" ] && [ "$${SLICERDDSURFER_XVFB_RUN}" != "none" ]; then \
	  env PATH="$$(dirname "$${SLICERDDSURFER_XVFB_RUN}"):$${PATH}" \
	    SLICERDDSURFER_EXTENSION_MODULE_DIR="$${SLICERDDSURFER_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules" \
	    "$${SLICERDDSURFER_XVFB_RUN}" -a "$${SLICERDDSURFER_SLICER_LAUNCHER}" --no-splash --disable-cli-modules \
	    --additional-module-paths "$${SLICERDDSURFER_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules" \
	    --python-script Testing/Python/slicer_extension_install_smoke.py; \
	elif [ "$${SLICERDDSURFER_USE_EXISTING_DISPLAY:-0}" = "1" ] || [ -n "$${DISPLAY:-}" ] || [ -n "$${WAYLAND_DISPLAY:-}" ]; then \
	  env SLICERDDSURFER_EXTENSION_MODULE_DIR="$${SLICERDDSURFER_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules" \
	    "$${SLICERDDSURFER_SLICER_LAUNCHER}" --no-splash --disable-cli-modules \
	    --additional-module-paths "$${SLICERDDSURFER_EXTENSION_INSTALL_ROOT:-/tmp/slicerdsurfer-extension-smoke}/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules" \
	    --python-script Testing/Python/slicer_extension_install_smoke.py; \
	else \
	  echo "Set SLICERDDSURFER_XVFB_RUN=/path/to/xvfb-run, or run inside an existing X/VNC session with SLICERDDSURFER_USE_EXISTING_DISPLAY=1."; \
	  exit 2; \
	fi

release-plan:
	: "$${SLICERDDSURFER_RELEASE_SUBJECT_ROOT:?Set SLICERDDSURFER_RELEASE_SUBJECT_ROOT to a subject-root fixture}"
	$(PYTHON) scripts/release_validation.py --subject-root "$${SLICERDDSURFER_RELEASE_SUBJECT_ROOT}" $(SLICERDDSURFER_RELEASE_ARGS)

release-check:
	$(PYTHON) scripts/release_audit.py
	$(PYTHON) scripts/download_model_assets.py --profile core --verify-only
	$(MAKE) release-plan

release-artifacts:
	$(PYTHON) scripts/build_release_artifacts.py \
	  --release-validation-report "$${SLICERDDSURFER_RELEASE_VALIDATION_REPORT:-/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/release_validation/release_validation_report.json}"

output-tree-report:
	$(PYTHON) Testing/Python/generate_output_tree_report.py \
	  --output-root "$${SLICERDDSURFER_OUTPUT_ROOT:-/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs}" \
	  --dest "$${SLICERDDSURFER_OUTPUT_TREE_HTML:-ignore/local_reports/SlicerDDSurfer_100307_release_candidate_output_tree.html}"

lint:
	$(PYTHON) -m ruff check .
