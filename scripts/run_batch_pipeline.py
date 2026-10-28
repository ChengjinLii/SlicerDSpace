#!/usr/bin/env python3
"""Batch runner for SlicerDSpace subject-root workflows."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.external_process import text_subprocess_kwargs
from shared.pipeline import RAW_INPUT_FILES, inspect_subject_directory, is_raw_subject_root


@dataclass(frozen=True)
class BatchSubject:
    subject_id: str
    subject_root: Path
    source: str
    mode: str


@dataclass(frozen=True)
class SubjectRunResult:
    subject_id: str
    subject_root: Path
    command: list[str]
    returncode: int
    stdout_log: Path
    stderr_log: Path
    elapsed_seconds: float


def _parse_jobs(value: str) -> int:
    jobs = int(value)
    if jobs < 1:
        raise argparse.ArgumentTypeError("batch size/jobs must be at least 1")
    return jobs


def _unique_path_candidates(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def _direct_raw_files(path: Path) -> bool:
    return path.is_dir() and all((path / filename).exists() for filename in RAW_INPUT_FILES.values())


def _arrange_subject_input(subject_dir: Path, mode: str) -> bool:
    if mode == "none" or is_raw_subject_root(subject_dir) or not _direct_raw_files(subject_dir):
        return False
    input_dir = subject_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    for filename in RAW_INPUT_FILES.values():
        source = subject_dir / filename
        target = input_dir / filename
        if target.exists():
            continue
        if mode == "copy":
            shutil.copy2(source, target)
        elif mode == "symlink":
            target.symlink_to(source)
        else:
            raise ValueError(f"Unsupported arrange mode: {mode}")
    return True


def _parse_subject_list(path: Path, batch_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for raw_line in path.expanduser().read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.replace(",", " ").split() if part.strip()]
        if not parts:
            continue
        value = parts[-1]
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = batch_root / candidate
        candidates.append(candidate)
    return candidates


def discover_subjects(
    batch_root: Path,
    *,
    subject_glob: str = "*",
    subject_list: Path | None = None,
    arrange_inputs: str = "none",
    include_missing: bool = False,
) -> tuple[list[BatchSubject], list[dict[str, str]]]:
    root = batch_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Batch root does not exist or is not a directory: {root}")

    if subject_list:
        candidates = _parse_subject_list(subject_list, root)
    else:
        candidates = [path for path in sorted(root.glob(subject_glob)) if path.is_dir()]
    candidates = _unique_path_candidates(candidates)

    subjects: list[BatchSubject] = []
    skipped: list[dict[str, str]] = []
    for candidate in candidates:
        arranged = _arrange_subject_input(candidate, arrange_inputs)
        subject_id = candidate.name
        inspected = inspect_subject_directory(candidate, subject_id)
        if inspected["mode"] == "missing":
            inspected = inspect_subject_directory(root, subject_id)
        if inspected["mode"] == "missing":
            skipped.append(
                {
                    "path": candidate.as_posix(),
                    "subject_id": subject_id,
                    "reason": "missing required input/data.nii.gz, bvals, or bvecs",
                }
            )
            if include_missing:
                subjects.append(BatchSubject(subject_id, candidate, "subject-list" if subject_list else "glob", "missing"))
            continue
        subject_root = Path(inspected["subject_root"] or inspected["subject_dir"]).expanduser().resolve()
        mode = str(inspected["mode"])
        if arranged:
            mode = f"{mode}+arranged"
        subjects.append(BatchSubject(subject_id, subject_root, "subject-list" if subject_list else "glob", mode))
    return subjects, skipped


def build_subject_command(
    subject: BatchSubject,
    *,
    pipeline_script: Path,
    python_executable: Path,
    output_root: Path | None,
    run_name: str,
    execute: bool,
    forwarded_args: list[str],
) -> list[str]:
    command = [
        str(python_executable.expanduser()),
        str(pipeline_script.expanduser()),
        "--subject-root",
        subject.subject_root.as_posix(),
        "--subject-id",
        subject.subject_id,
        "--run-name",
        run_name,
    ]
    if output_root is not None:
        command.extend(["--output-root", (output_root.expanduser().resolve() / subject.subject_id).as_posix()])
    if execute:
        command.append("--execute")
    command.extend(forwarded_args)
    return command


def _run_subject(command: list[str], subject: BatchSubject, log_dir: Path) -> SubjectRunResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in subject.subject_id)
    stdout_log = log_dir / f"{safe_id}.stdout.log"
    stderr_log = log_dir / f"{safe_id}.stderr.log"
    started = time.time()
    # Stream independent logs so a long cohort does not retain every process's
    # output in the batch driver's memory, and logs are readable during a run.
    with stdout_log.open("w", encoding="utf-8") as stdout, stderr_log.open("w", encoding="utf-8") as stderr:
        try:
            completed = subprocess.run(command, stdout=stdout, stderr=stderr, **text_subprocess_kwargs())
        except OSError as exc:
            stderr.write(f"Could not start subject process: {exc}\n")
            completed = subprocess.CompletedProcess(command, 127)
    return SubjectRunResult(
        subject_id=subject.subject_id,
        subject_root=subject.subject_root,
        command=command,
        returncode=completed.returncode,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
        elapsed_seconds=round(time.time() - started, 3),
    )


def _write_manifest(path: Path, payload: dict[str, object]) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run SlicerDSpace over a directory of subject roots. Unknown options are forwarded "
            "unchanged to every subject CLI, for example --all, --targets, --brain-mask-backend, "
            "--pnl-mask-python, --pnl-mask-script, --pnl-mask-model-dir, --pnl-mask-ants-bin-dir, "
            "--postprocess-freesurfer-home, or other external paths."
            " Microstructure defaults to DTI only; --microstructure-stages, --run-free-water, "
            "--run-noddi, --run-dki, --dki-fit-method, --dki-matlab-executable and --dki-mkcurve-root "
            "are forwarded unchanged."
        )
    )
    parser.add_argument("--batch-root", required=True, type=Path, help="Directory containing one subdirectory per subject.")
    parser.add_argument("--subject-glob", default="*", help="Glob used under --batch-root when --subject-list is omitted.")
    parser.add_argument("--subject-list", type=Path, help="Optional text file listing subject directories or relative IDs.")
    parser.add_argument("--output-root", type=Path, help="Batch output root. Each subject writes under <output-root>/<subject-id>.")
    parser.add_argument("--run-name", default="Test1", help="Run name forwarded to each subject. Defaults to Test1.")
    parser.add_argument("--jobs", "--batch-size", dest="jobs", type=_parse_jobs, default=1, help="Concurrent subject count.")
    parser.add_argument("--execute", action="store_true", help="Actually execute each subject. Omit for dry-run planning.")
    parser.add_argument(
        "--arrange-inputs",
        choices=("none", "symlink", "copy"),
        default="none",
        help="Optionally create subject/input from raw files placed directly in each subject directory.",
    )
    parser.add_argument("--include-missing", action="store_true", help="Include missing subjects in the manifest instead of only skipped.")
    parser.add_argument("--continue-on-error", action="store_true", help="Keep launching remaining subjects after failures. Otherwise, finish and record active subjects, then stop.")
    parser.add_argument("--manifest", type=Path, help="Batch manifest path. Defaults under output root or batch root.")
    parser.add_argument("--log-dir", type=Path, help="Per-subject stdout/stderr log directory.")
    parser.add_argument(
        "--pipeline-script",
        type=Path,
        default=REPO_ROOT / "shared" / "run_subject_pipeline_cli.py",
        help="Subject-level CLI script to execute.",
    )
    parser.add_argument("--python-executable", type=Path, default=Path(sys.executable), help="Python executable for subject CLI.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, forwarded_args = parser.parse_known_args(argv)

    try:
        subjects, skipped = discover_subjects(
            args.batch_root,
            subject_glob=args.subject_glob,
            subject_list=args.subject_list,
            arrange_inputs=args.arrange_inputs,
            include_missing=args.include_missing,
        )
    except Exception as exc:
        parser.error(str(exc))

    ids: dict[str, Path] = {}
    for subject in subjects:
        if subject.subject_id in ids:
            parser.error(f"Duplicate subject ID {subject.subject_id!r}: {ids[subject.subject_id]} and {subject.subject_root}")
        ids[subject.subject_id] = subject.subject_root

    output_base = args.output_root.expanduser().resolve() if args.output_root else args.batch_root.expanduser().resolve() / "batch_outputs"
    manifest_path = args.manifest or output_base / "00_batch_metadata" / f"batch_{time.strftime('%Y%m%d_%H%M%S')}.json"
    log_dir = args.log_dir.expanduser().resolve() if args.log_dir else manifest_path.expanduser().resolve().parent / "logs"

    runnable_subjects = [subject for subject in subjects if subject.mode != "missing"]
    subject_commands = [
        (
            subject,
            build_subject_command(
                subject,
                pipeline_script=args.pipeline_script,
                python_executable=args.python_executable,
                output_root=output_base if args.output_root else None,
                run_name=args.run_name,
                execute=bool(args.execute),
                forwarded_args=list(forwarded_args),
            ),
        )
        for subject in runnable_subjects
    ]

    planned_commands = [
        build_subject_command(
            subject,
            pipeline_script=args.pipeline_script,
            python_executable=args.python_executable,
            output_root=output_base if args.output_root else None,
            run_name=args.run_name,
            execute=bool(args.execute),
            forwarded_args=list(forwarded_args),
        )
        for subject in runnable_subjects
    ]

    result_payloads: list[dict[str, object]] = []
    failures = 0
    started = time.time()
    if subject_commands:
        pending_subjects = iter(subject_commands)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_to_subject: dict[concurrent.futures.Future[SubjectRunResult], BatchSubject] = {}

            def submit_next() -> bool:
                try:
                    subject, command = next(pending_subjects)
                except StopIteration:
                    return False
                future_to_subject[executor.submit(_run_subject, command, subject, log_dir)] = subject
                return True

            for _ in range(min(args.jobs, len(subject_commands))):
                submit_next()

            stop_submitting = False
            while future_to_subject:
                done, _pending = concurrent.futures.wait(
                    future_to_subject,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                for future in done:
                    future_to_subject.pop(future)
                    result = future.result()
                    if result.returncode != 0:
                        failures += 1
                        stop_submitting = not args.continue_on_error
                    result_payloads.append(
                        {
                            "subject_id": result.subject_id,
                            "subject_root": result.subject_root.as_posix(),
                            "returncode": result.returncode,
                            "elapsed_seconds": result.elapsed_seconds,
                            "command": result.command,
                            "stdout_log": result.stdout_log.as_posix(),
                            "stderr_log": result.stderr_log.as_posix(),
                        }
                    )
                # Drain active processes after a failure so their outputs and
                # exit states remain in the batch record; stop only new launches.
                while not stop_submitting and len(future_to_subject) < args.jobs and submit_next():
                    pass

    payload: dict[str, object] = {
        "kind": "slicerdsurfer_batch_run",
        "version": 1,
        "batch_root": args.batch_root.expanduser().resolve().as_posix(),
        "output_root": output_base.as_posix() if args.output_root else None,
        "run_name": args.run_name,
        "execute": bool(args.execute),
        "jobs": args.jobs,
        "forwarded_args": forwarded_args,
        "arrange_inputs": args.arrange_inputs,
        "subjects": [
            {
                "subject_id": subject.subject_id,
                "subject_root": subject.subject_root.as_posix(),
                "source": subject.source,
                "mode": subject.mode,
            }
            for subject in subjects
        ],
        "skipped": skipped,
        "planned_commands": planned_commands,
        "results": sorted(result_payloads, key=lambda item: str(item["subject_id"])),
        "not_launched": [subject.subject_id for subject in runnable_subjects
                         if subject.subject_id not in {str(item["subject_id"]) for item in result_payloads}],
        "status": "failed" if failures else ("completed" if args.execute else "planned") if result_payloads else "empty",
        "elapsed_seconds": round(time.time() - started, 3),
        "manifest_path": "",
    }
    written_manifest = _write_manifest(manifest_path, payload)
    payload["manifest_path"] = written_manifest.as_posix()
    _write_manifest(written_manifest, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    # Machine-readable line for callers (e.g. the Slicer widget's background
    # QProcess reader) that watch stdout for a manifest path: unlike the
    # single-subject pipeline CLI's manifest, this file is not named
    # "*_orchestration_manifest.json", so it needs an explicit marker.
    print(f"[Batch] manifest: {written_manifest.as_posix()}")
    print(written_manifest.as_posix(), file=sys.stderr)

    if failures:
        return 2
    if not subjects:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
