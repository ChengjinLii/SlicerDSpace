"""Short-lived input-layout reuse for GUI feedback, never worker preflight."""

from pathlib import Path
from time import monotonic


class InputInspectionCache:
    def __init__(self, inspector, *, ttl_seconds=1.0, clock=monotonic):
        self._inspector = inspector
        self._ttl = ttl_seconds
        self._clock = clock
        self._entry = None

    @staticmethod
    def _stamp(path):
        try:
            stat = path.stat()
            return stat.st_dev, stat.st_ino, stat.st_mode, stat.st_mtime_ns, stat.st_ctime_ns
        except OSError:
            return None

    def _stamps(self, root, subject_id):
        subject = root / subject_id
        # Shallow changes invalidate immediately; nested DICOM header changes
        # expire after one second. Run always bypasses this display-only cache.
        paths = [root, root / "input", subject, subject / "input"]
        # Directory timestamps alone can miss rapid changes on coarse clocks.
        paths.extend(folder / name for folder in (root / "input", subject / "input")
                     for name in ("data.nii.gz", "bvals", "bvecs"))
        return tuple(self._stamp(path) for path in paths)

    def inspect(self, candidate, subject_id, *, refresh=False):
        root = Path(candidate).expanduser()
        if not root.is_absolute():
            root = root.absolute()
        key = str(root), subject_id
        now = self._clock()
        if not refresh and self._entry is not None:
            previous_key, checked_at, stamps, result = self._entry
            if (key == previous_key and 0 <= now - checked_at < self._ttl
                    and stamps == self._stamps(root, subject_id)):
                return dict(result)
        self._entry = None
        result = dict(self._inspector(root, subject_id))
        # Canonical and legacy layouts already use cheap file-existence checks.
        # Keep them fresh rather than paying extra fingerprint overhead.
        if result.get("mode") in {"dicom", "missing"}:
            self._entry = key, self._clock(), self._stamps(root, subject_id), result
        return dict(result)


def inspect_input_directory(owner, candidate, subject_id, *, refresh=False):
    cache = getattr(owner, "_inputInspectionCache", None)
    if cache is None:
        from shared.pipeline import inspect_subject_directory

        cache = owner._inputInspectionCache = InputInspectionCache(inspect_subject_directory)
    return cache.inspect(candidate, subject_id, refresh=refresh)
