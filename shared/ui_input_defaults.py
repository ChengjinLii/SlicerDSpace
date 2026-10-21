"""Conservative defaults for the subject-folder picker, without data edits."""

from pathlib import Path


def subject_folder_defaults(path, subject_id="", *, batch=False):
    root = Path(path).expanduser() if path else None
    if root is None or not root.is_dir():
        return path or "", subject_id
    if not batch and root.name == "input" and all((root / name).is_file() for name in ("data.nii.gz", "bvals", "bvecs")):
        root = root.parent
    inferred = subject_id
    if not batch and not str(subject_id).strip():
        inferred = root.name
    return str(root), inferred
