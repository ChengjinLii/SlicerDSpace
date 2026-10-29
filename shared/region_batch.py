"""Apply one optional region request to completed subject runs, without refitting."""

from pathlib import Path

from shared.region_analysis import inspect_run, read_json, run_analysis, write_json
from shared.region_reports import write_table
from shared.region_selection import resolve_regions


def run_region_batch(config):
    subjects = config.get("subjects")
    template = config.get("request")
    if not isinstance(subjects, list) or not subjects or not isinstance(template, dict):
        raise ValueError("Batch requires a request object and a nonempty subjects list")
    forbidden = {"output_dir", "source_manifest", "manifest_sha256", "atlas_sha256", "lut_sha256"}
    if forbidden & template.keys():
        raise ValueError("Keep per-subject paths/hashes outside the shared batch request")
    root = Path(config["output_dir"]).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Choose a fresh batch output directory")
    root.mkdir(parents=True, exist_ok=True)
    records, tables, reference = [], {}, None
    summary = dict(kind="slicerdspace_regional_batch", status="running", subjects=records)
    manifest = root / "regional_batch_manifest.json"
    write_json(manifest, summary)
    for index, subject in enumerate(subjects):
        try:
            if not isinstance(subject, dict) or "source_manifest" not in subject:
                raise ValueError("Each subject requires source_manifest")
            if set(subject) - {"source_manifest", "atlas_override", "lut_path"}:
                raise ValueError("Subject overrides support only source_manifest, atlas_override and lut_path")
            request = {**template, **subject, "output_dir": str(root / f"subject-{index + 1:04d}")}
            catalog = inspect_run(request["source_manifest"], atlas_override=request.get("atlas_override"),
                                  lut_path=request.get("lut_path"))
            labels = set()
            for key in ("selected", "target", "include", "exclude"):
                labels.update(resolve_regions(catalog["regions"], request.get(key + "_regions", request.get(key + "_labels")),
                                              allow_empty=key != "selected"))
            semantic_labels = [(row["id"], row["name"]) for row in catalog["regions"] if row["id"] in labels]
            if reference is not None and semantic_labels != reference:
                raise ValueError("Selected atlas IDs/names differ between subjects; use a compatible atlas/LUT")
            for key in ("manifest_sha256", "atlas_sha256", "lut_sha256"):
                request[key] = catalog[key]
            path = run_analysis(request)
            reference = semantic_labels
            record = read_json(path)
            records.append(dict(status="completed", subject_id=catalog["subject_id"], manifest=str(path)))
            import csv

            for filename in ("selected_regions.csv", "selected_microstructure.csv", "selected_tissue_statistics.csv",
                             "selected_surface_statistics.csv", "bilateral_statistics.csv", "selected_region_connections.csv"):
                source = path.parent / filename
                if not source.is_file():
                    continue
                with source.open(encoding="utf-8", newline="") as stream:
                    for row in csv.DictReader(stream):
                        tables.setdefault(filename, []).append(dict(subject_id=catalog["subject_id"],
                            source_manifest=catalog["source_manifest"], atlas_sha256=catalog["atlas_sha256"], **row))
        except KeyboardInterrupt:
            records.append(dict(status="cancelled", source_manifest=subject.get("source_manifest"), error="Cancelled"))
            summary["status"] = "cancelled"
            write_json(manifest, summary)
            raise
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            records.append(dict(status="failed", source_manifest=subject.get("source_manifest") if isinstance(subject, dict) else None,
                                error=str(exc)))
        write_json(manifest, summary)
    for filename, rows in tables.items():
        fields = list(dict.fromkeys(key for row in rows for key in row))
        write_table(root / ("cohort_" + filename), rows, fields)
    summary.update(status="completed" if all(row["status"] == "completed" for row in records) else "partial_failed",
                   completed_subjects=sum(row["status"] == "completed" for row in records), total_subjects=len(records))
    write_json(manifest, summary)
    return manifest
