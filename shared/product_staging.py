"""Publish fresh external-backend products without treating stale files as new."""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import uuid


def _stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:8]


def archive_run_records(output_dir, names):
    existing = [Path(output_dir) / name for name in names if (Path(output_dir) / name).is_file()]
    if not existing:
        return None
    archive = Path(output_dir) / '.previous_records' / _stamp()
    archive.mkdir(parents=True)
    for path in existing:
        shutil.copy2(path, archive / path.name)
    return str(archive)


def new_product_staging(output_dir, backend):
    return Path(tempfile.mkdtemp(prefix=f'.{Path(output_dir).name}-{backend}-', dir=Path(output_dir).parent))


def publish_products(staging, output_dir, previous_names=()):
    """Move previous products to an excluded archive, then publish the new set."""
    staging, output_dir = Path(staging), Path(output_dir)
    products = list(staging.iterdir())
    old_names = set(previous_names) | {path.name for path in products}
    previous = [output_dir / name for name in sorted(old_names) if (output_dir / name).exists()]
    archive = output_dir / '.previous_products' / _stamp()
    if previous:
        archive.mkdir(parents=True)
        for path in previous:
            shutil.move(str(path), str(archive / path.name))
    try:
        for path in products:
            shutil.move(str(path), str(output_dir / path.name))
    except Exception:
        # Retain all evidence even if publication fails. No prior data is deleted.
        raise
    staging.rmdir()
    return str(archive) if previous else None


def retain_failed_products(staging, output_dir):
    destination = Path(output_dir) / '.failed_products' / _stamp()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staging), str(destination))
    return destination
