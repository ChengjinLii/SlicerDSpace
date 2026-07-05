"""Repository documentation path helpers."""

from __future__ import annotations

from pathlib import Path


DOC_PATHS = {
    "external_dependencies": Path("docs/setup/EXTERNAL_DEPENDENCIES.md"),
    "model_assets": Path("docs/assets/MODEL_ASSETS.md"),
    "model_asset_terms": Path("docs/assets/MODEL_ASSET_TERMS.md"),
    "model_asset_hosting": Path("docs/assets/MODEL_ASSET_HOSTING_PLAN.md"),
    "product_architecture": Path("docs/architecture/PRODUCT_ARCHITECTURE.md"),
    "release": Path("docs/release/RELEASE.md"),
    "release_candidate_validation": Path("docs/release/RELEASE_CANDIDATE_VALIDATION.md"),
    "release_notes": Path("docs/release/RELEASE_NOTES_v0.1.0.md"),
    "github_release_draft": Path("docs/release/GITHUB_RELEASE_DRAFT_v0.1.0.md"),
    "doi_archive_prep": Path("docs/release/DOI_ARCHIVE_PREP.md"),
}


def doc_path(repo_root: Path, key: str) -> Path:
    """Return an absolute path for a known repository documentation file."""

    return repo_root / DOC_PATHS[key]
