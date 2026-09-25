#!/usr/bin/env python3
"""Tests for manifest-driven model asset downloads."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "download_model_assets.py"


def _load_downloader_module():
    spec = importlib.util.spec_from_file_location("download_model_assets", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelAssetsTest(unittest.TestCase):
    def test_default_model_asset_root_is_user_data_directory(self) -> None:
        from shared.model_assets import MODEL_ASSETS_ENV, configured_model_assets_root

        previous = os.environ.pop(MODEL_ASSETS_ENV, None)
        try:
            root = configured_model_assets_root()
        finally:
            if previous is not None:
                os.environ[MODEL_ASSETS_ENV] = previous

        self.assertIn("SlicerDDSurfer", root.as_posix())
        self.assertNotEqual(root, REPO_ROOT)

    def test_explicit_model_asset_root_wins(self) -> None:
        from shared.model_assets import configured_model_assets_root

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(configured_model_assets_root(Path(tmp)), Path(tmp).resolve())

    def test_core_profile_resolves_manifest_includes_and_required_paths(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "core")

        self.assertEqual(plan.profile, "core")
        self.assertIn("surface", plan.resolved_profiles)
        self.assertIn("segmentation/weights/**", plan.include_patterns)
        self.assertIn("parcellation/weights/**", plan.include_patterns)
        self.assertIn("segmentation/weights/dti_axial.pt", plan.required_paths)
        self.assertIn("segmentation/weights/dti_axial.pt", plan.asset_records)
        self.assertIn("sha256", plan.asset_records["segmentation/weights/dti_axial.pt"])
        self.assertIn("github_lfs", plan.source_ids)
        self.assertIn("slicerdsurfer_models_git", plan.source_ids)
        self.assertIn("DDSURFER_CHECKPOINT_DIR", plan.external_overrides)
        self.assertIn("DDCSR surface model weights", plan.asset_groups)
        self.assertTrue(any("redistribution" in notice for notice in plan.terms_notices))

    def test_manifest_prefers_independent_model_repository_source(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        sources = manifest["asset_sources"]

        self.assertEqual(manifest["default_asset_source_ids"][0], "slicerdsurfer_models_git")
        self.assertEqual(sources["slicerdsurfer_models_git"]["status"], "active")
        self.assertIn(
            "https://github.com/ChengjinLii/SlicerDDSurfer-models/raw/main",
            sources["slicerdsurfer_models_git"]["url_template"],
        )

    def test_quick_gate_alias_resolves_to_core_profile(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "quick-gate")

        self.assertEqual(plan.profile, "quick-gate")
        self.assertIn("core", plan.resolved_profiles)
        self.assertIn("surface", plan.resolved_profiles)
        self.assertIn("parcellation/weights/**", plan.include_patterns)
        self.assertIn("segmentation/weights/dti_sagittal.pt", plan.required_paths)

    def test_verify_asset_plan_reports_missing_and_lfs_pointer_files(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt", "weights/missing.pt"),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("github_lfs",),
                asset_records={},
            )

            asset.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n", encoding="utf-8")
            result = module.verify_asset_plan(root, plan)
            self.assertIn("weights/model.pt", result["lfs_pointers"])
            self.assertIn("weights/missing.pt", result["missing"])
            self.assertFalse(result["ok"])

            (root / "weights" / "missing.pt").write_text("downloaded", encoding="utf-8")
            asset.write_text("downloaded", encoding="utf-8")
            result = module.verify_asset_plan(root, plan)
            self.assertTrue(result["ok"])

    def test_asset_lockfile_records_sha256_and_terms(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            asset.write_text("downloaded", encoding="utf-8")
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=("unit weights",),
                terms_notices=("confirm terms",),
                source_ids=("mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["mirror"],
                        "size_bytes": len("downloaded"),
                    }
                },
            )

            lockfile = module.build_asset_lockfile(root, plan)

            self.assertEqual(lockfile["schema"], "slicerddsurfer.model_assets.lockfile.v1")
            self.assertEqual(lockfile["asset_groups"], ["unit weights"])
            self.assertEqual(lockfile["terms_notices"], ["confirm terms"])
            self.assertEqual(lockfile["records"][0]["path"], "weights/model.pt")
            self.assertFalse(lockfile["records"][0]["lfs_pointer"])
            self.assertIsNotNone(lockfile["records"][0]["sha256"])
            self.assertEqual(lockfile["records"][0]["source_ids"], ["mirror"])

    def test_verify_asset_plan_reports_size_and_sha256_mismatches(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            asset.write_text("bad", encoding="utf-8")
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["mirror"],
                        "size_bytes": 10,
                        "sha256": "0" * 64,
                    }
                },
            )

            result = module.verify_asset_plan(root, plan)

        self.assertFalse(result["ok"])
        self.assertEqual(result["hashes_checked"], 1)
        self.assertEqual(result["size_mismatches"][0]["path"], "weights/model.pt")
        self.assertEqual(result["sha256_mismatches"][0]["path"], "weights/model.pt")

    def test_verify_asset_plan_can_skip_hashes_for_ui_status(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            asset.write_text("downloaded", encoding="utf-8")
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["mirror"],
                        "size_bytes": asset.stat().st_size,
                        "sha256": "0" * 64,
                    }
                },
            )

            result = module.verify_asset_plan(root, plan, check_hashes=False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["hashes_checked"], 0)

    def test_url_download_uses_base_url_and_verifies_checksum(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            mirror = tmp_path / "mirror"
            source_file = mirror / "weights" / "model.pt"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("downloaded", encoding="utf-8")
            expected_sha = module._sha256(source_file)
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("unit_mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["unit_mirror"],
                        "size_bytes": source_file.stat().st_size,
                        "sha256": expected_sha,
                    }
                },
            )
            manifest = {
                "asset_sources": {},
            }

            module.download_asset_plan(
                repo_root,
                plan,
                manifest,
                source="url",
                base_urls=(mirror.resolve().as_uri(),),
            )
            result = module.verify_asset_plan(repo_root, plan)

        self.assertTrue(result["ok"])

    def test_url_download_reports_file_and_byte_progress(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            mirror = tmp_path / "mirror"
            source_file = mirror / "weights" / "model.pt"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(b"model-data" * 1024)
            source_size = source_file.stat().st_size
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("unit_mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["unit_mirror"],
                        "size_bytes": source_size,
                        "sha256": module._sha256(source_file),
                    }
                },
            )
            events = []

            module.download_asset_plan(
                repo_root,
                plan,
                {"asset_sources": {}},
                source="url",
                base_urls=(mirror.resolve().as_uri(),),
                progress_callback=events.append,
            )

        self.assertTrue(any(event["phase"] == "downloading" for event in events))
        complete = next(event for event in events if event["phase"] == "complete")
        self.assertEqual(complete["path"], "weights/model.pt")
        self.assertEqual(complete["downloaded_bytes"], source_size)
        self.assertEqual(complete["total_bytes"], source_size)
        self.assertEqual(complete["file_index"], 1)
        self.assertEqual(complete["file_count"], 1)

    def test_cancelled_download_keeps_partial_file_for_resume(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            target = root / "target.bin"
            source.write_bytes(b"x" * (3 * 1024 * 1024))
            cancel = {"requested": False}

            def on_progress(event) -> None:
                if event["phase"] == "downloading" and event["downloaded_bytes"] >= 1024 * 1024:
                    cancel["requested"] = True

            with self.assertRaises(module.DownloadCancelledError):
                module._download_url_to_path(
                    source.resolve().as_uri(),
                    target,
                    relative_path="weights/model.bin",
                    expected_size=source.stat().st_size,
                    progress_callback=on_progress,
                    cancel_check=lambda: cancel["requested"],
                )

            partial = target.with_name(target.name + ".part")
            self.assertTrue(partial.is_file())
            self.assertGreaterEqual(partial.stat().st_size, 1024 * 1024)
            self.assertFalse(target.exists())

    def test_content_range_starts_at_validates_rfc7233_header(self) -> None:
        module = _load_downloader_module()

        self.assertTrue(module._content_range_starts_at("bytes 100-999/1000", 100))
        self.assertFalse(module._content_range_starts_at("bytes 0-999/1000", 100))
        self.assertFalse(module._content_range_starts_at("", 100))
        self.assertFalse(module._content_range_starts_at("not-a-content-range", 100))

    def test_oversized_part_file_is_discarded_and_download_restarts(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(b"x" * 1000)  # larger than expected_size below
            source = root / "source.bin"
            source.write_bytes(b"y" * 10)

            module._download_url_to_path(
                source.resolve().as_uri(),
                target,
                relative_path="weights/model.bin",
                expected_size=10,
            )

            self.assertEqual(target.read_bytes(), b"y" * 10)
            self.assertFalse(partial.exists())

    def test_mismatched_content_range_on_resume_raises_and_keeps_part_untouched(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(b"a" * 100)
            original_partial_bytes = partial.read_bytes()

            fake_response = mock.MagicMock()
            fake_response.status = 206
            fake_response.headers = {"Content-Range": "bytes 0-899/900", "Content-Length": "900"}
            fake_response.read.return_value = b""
            fake_response.__enter__.return_value = fake_response
            fake_response.__exit__.return_value = False

            with mock.patch("urllib.request.urlopen", return_value=fake_response):
                with self.assertRaises(module.DownloadIntegrityError):
                    module._download_url_to_path(
                        "https://example.invalid/weights/model.bin",
                        target,
                        relative_path="weights/model.bin",
                        expected_size=900,
                    )

            self.assertFalse(target.exists())
            self.assertTrue(partial.is_file())
            self.assertEqual(partial.read_bytes(), original_partial_bytes)

    def test_416_response_discards_stale_part_and_raises(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(b"a" * 5)

            import io

            http_error = module.urllib.error.HTTPError(
                "https://example.invalid/weights/model.bin", 416, "Range Not Satisfiable", {}, io.BytesIO(b"")
            )
            self.addCleanup(http_error.close)

            with mock.patch("urllib.request.urlopen", side_effect=http_error):
                with self.assertRaises(module.DownloadIntegrityError):
                    module._download_url_to_path(
                        "https://example.invalid/weights/model.bin",
                        target,
                        relative_path="weights/model.bin",
                        expected_size=5,
                    )

            self.assertFalse(partial.exists())
            self.assertFalse(target.exists())

    def test_incomplete_read_keeps_part_file_for_resume(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            partial = target.with_name(target.name + ".part")

            fake_response = mock.MagicMock()
            fake_response.status = None
            fake_response.headers = {"Content-Length": "1000"}
            fake_response.read.side_effect = [
                b"first-chunk-bytes",
                http.client.IncompleteRead(b"partial", expected=500),
            ]
            fake_response.__enter__.return_value = fake_response
            fake_response.__exit__.return_value = False

            with mock.patch("urllib.request.urlopen", return_value=fake_response):
                with self.assertRaises(module.DownloadIntegrityError):
                    module._download_url_to_path(
                        "https://example.invalid/weights/model.bin",
                        target,
                        relative_path="weights/model.bin",
                        expected_size=1000,
                    )

            self.assertFalse(target.exists())
            self.assertTrue(partial.is_file())
            self.assertEqual(partial.read_bytes(), b"first-chunk-bytes")

    def test_short_read_without_server_error_does_not_promote_the_part_file(self) -> None:
        # Simulates a connection that closes cleanly (empty read = EOF) but
        # before delivering all the bytes the server itself declared -- no
        # exception is raised by http.client, so this must be caught by the
        # downloaded/expected_total size check, not by exception handling.
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            partial = target.with_name(target.name + ".part")

            fake_response = mock.MagicMock()
            fake_response.status = None
            fake_response.headers = {"Content-Length": "1000"}
            fake_response.read.side_effect = [b"only-part-of-the-data", b""]
            fake_response.__enter__.return_value = fake_response
            fake_response.__exit__.return_value = False

            with mock.patch("urllib.request.urlopen", return_value=fake_response):
                with self.assertRaises(module.DownloadIntegrityError):
                    module._download_url_to_path(
                        "https://example.invalid/weights/model.bin",
                        target,
                        relative_path="weights/model.bin",
                        expected_size=1000,
                    )

            self.assertFalse(target.exists())
            self.assertTrue(partial.is_file())
            self.assertEqual(partial.read_bytes(), b"only-part-of-the-data")

    def test_force_discards_a_stale_part_file_before_redownloading(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            mirror = tmp_path / "mirror"
            source_file = mirror / "weights" / "model.pt"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(b"the-real-content")
            target = repo_root / "weights" / "model.pt"
            stale_part = target.with_name(target.name + ".part")
            stale_part.parent.mkdir(parents=True)
            stale_part.write_bytes(b"leftover-garbage-from-a-previous-attempt")
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("unit_mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["unit_mirror"],
                        "size_bytes": source_file.stat().st_size,
                        "sha256": module._sha256(source_file),
                    }
                },
            )

            module.download_asset_urls(
                repo_root,
                plan,
                {"asset_sources": {}},
                source_ids=("unit_mirror",),
                base_urls=(mirror.resolve().as_uri(),),
                allow_planned_sources=True,
                force=True,
            )

            self.assertEqual(target.read_bytes(), b"the-real-content")
            self.assertFalse(stale_part.exists())

    def test_model_asset_setup_guidance_summarizes_missing_assets(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "core")
        verification = {
            "missing": ["segmentation/weights/dti_axial.pt"],
            "lfs_pointers": ["parcellation/weights/Fused-Unet-v3-noMax-axial.pkl"],
            "size_mismatches": [],
            "sha256_mismatches": [],
        }

        guidance = module.model_asset_setup_guidance(plan, manifest, verification)

        self.assertEqual(guidance["profile"], "core")
        self.assertGreater(guidance["required_file_count"], 0)
        self.assertIn("slicerdsurfer_models_git", guidance["active_url_sources"])
        self.assertIn("--source-id slicerdsurfer_models_git", guidance["recommended_command"])
        self.assertIn("--asset-root", guidance["recommended_command"])
        self.assertIn("target_asset_root", guidance)
        self.assertEqual(guidance["missing_count"], 1)
        self.assertEqual(guidance["lfs_pointer_count"], 1)
        self.assertIn("segmentation/weights/dti_axial.pt", guidance["examples"]["missing"])

    def test_sentinel_profile_is_tiny_url_download_check(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "sentinel")

        self.assertEqual(plan.required_paths, ("sentinel/slicerdsurfer_sentinel.txt",))
        self.assertEqual(plan.asset_groups, ("download sentinel",))
        self.assertLess(plan.asset_records["sentinel/slicerdsurfer_sentinel.txt"]["size_bytes"], 1024)
        self.assertEqual(plan.source_ids, ("slicerdsurfer_models_git",))


class ModelAssetRootSecurityTest(unittest.TestCase):
    """shared.model_assets: narrowed automatic scan roots + sha256 gating.

    Regression coverage for removing the hardcoded, guessable shared/dev
    scan paths (e.g. /data/shared/..., /opt/..., a specific developer's home
    directory) and for verifying resolved asset roots against
    models/assets_manifest.json before trusting them.
    """

    def setUp(self) -> None:
        import shared.model_assets as model_assets_module

        self.model_assets_module = model_assets_module
        # Isolate the in-process sha256 cache and its on-disk path so tests
        # never touch the real user config directory or leak state between
        # tests (the cache is a lazily-initialized module-level singleton).
        self._cache_tmp = tempfile.TemporaryDirectory()
        self._cache_path = Path(self._cache_tmp.name) / "model_asset_sha256_cache.json"
        model_assets_module._SHA256_CACHE = None
        self._cache_path_patch = mock.patch.object(
            model_assets_module, "_sha256_cache_path", return_value=self._cache_path
        )
        self._cache_path_patch.start()

    def tearDown(self) -> None:
        self._cache_path_patch.stop()
        self.model_assets_module._SHA256_CACHE = None
        self._cache_tmp.cleanup()

    def _write_manifest(self, repo_root: Path, records: dict) -> None:
        manifest_dir = repo_root / "models"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "assets_manifest.json").write_text(
            json.dumps({"asset_records": records}), encoding="utf-8"
        )

    def test_common_model_asset_roots_has_no_hardcoded_shared_or_dev_paths(self) -> None:
        roots = self.model_assets_module.common_model_asset_roots()

        self.assertEqual(roots, (self.model_assets_module.default_user_model_assets_root(),))
        for forbidden in ("/data/", "/opt/", "/Users/Shared", "chengjin", "/usr/local/share"):
            for root in roots:
                self.assertNotIn(forbidden, root.as_posix())

    def test_model_asset_path_raises_on_a_file_that_fails_sha256_verification(self) -> None:
        # resolve_model_assets_root() still legitimately falls back to the
        # user's own default directory even when nothing there verifies
        # (that default is also the intended download target when nothing
        # has been fetched yet). The hard security boundary is
        # model_asset_path(): callers hand its result straight to
        # torch.load(), so an existing-but-tampered file there must raise
        # rather than be silently returned.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            user_root = tmp_path / "user-assets"
            repo_root = tmp_path / "repo"
            planted = user_root / "segmentation" / "weights" / "dti_axial.pt"
            planted.parent.mkdir(parents=True)
            planted.write_bytes(b"a planted, untrusted checkpoint")
            # The manifest expects a different digest than what was planted.
            self._write_manifest(
                repo_root,
                {"segmentation/weights/dti_axial.pt": {"sha256": "0" * 64}},
            )

            with mock.patch.object(
                self.model_assets_module, "default_user_model_assets_root", return_value=user_root
            ):
                with self.assertRaises(self.model_assets_module.ModelAssetIntegrityError):
                    self.model_assets_module.model_asset_path("segmentation/weights", repo_root=repo_root)

    def test_resolve_accepts_a_root_whose_required_file_matches_the_manifest(self) -> None:
        from shared.model_asset_integrity import sha256_of_file

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            user_root = tmp_path / "user-assets"
            repo_root = tmp_path / "repo"
            genuine = user_root / "segmentation" / "weights" / "dti_axial.pt"
            genuine.parent.mkdir(parents=True)
            genuine.write_bytes(b"the real, trusted checkpoint bytes")
            self._write_manifest(
                repo_root,
                {"segmentation/weights/dti_axial.pt": {"sha256": sha256_of_file(genuine)}},
            )

            with mock.patch.object(
                self.model_assets_module, "default_user_model_assets_root", return_value=user_root
            ):
                resolved = self.model_assets_module.resolve_model_assets_root(
                    repo_root=repo_root, required_paths=("segmentation/weights",)
                )
                asset_path = self.model_assets_module.model_asset_path(
                    "segmentation/weights", repo_root=repo_root
                )

            self.assertEqual(resolved, user_root.resolve())
            self.assertEqual(asset_path, user_root.resolve() / "segmentation" / "weights")

    def test_explicit_root_bypasses_verification(self) -> None:
        # An explicitly user-supplied root is the user's own informed
        # choice, not an automatically-guessed path; it is trusted directly.
        with tempfile.TemporaryDirectory() as tmp:
            explicit_root = Path(tmp) / "explicit-assets"
            explicit_root.mkdir()

            resolved = self.model_assets_module.resolve_model_assets_root(
                explicit=explicit_root, required_paths=("segmentation/weights",)
            )

            self.assertEqual(resolved, explicit_root.resolve())

    def test_directory_with_no_manifest_coverage_falls_back_to_plain_existence(self) -> None:
        # A required directory the manifest does not track at all (nothing
        # recorded to verify against) keeps the old, best-effort behavior.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            user_root = tmp_path / "user-assets"
            repo_root = tmp_path / "repo"
            unlisted_dir = user_root / "Resources" / "Data" / "unlisted"
            unlisted_dir.mkdir(parents=True)
            (unlisted_dir / "some_file.bin").write_bytes(b"not tracked by the manifest")
            self._write_manifest(repo_root, {})

            with mock.patch.object(
                self.model_assets_module, "default_user_model_assets_root", return_value=user_root
            ):
                resolved = self.model_assets_module.resolve_model_assets_root(
                    repo_root=repo_root, required_paths=("Resources/Data/unlisted",)
                )

            self.assertEqual(resolved, user_root.resolve())


if __name__ == "__main__":
    unittest.main()
