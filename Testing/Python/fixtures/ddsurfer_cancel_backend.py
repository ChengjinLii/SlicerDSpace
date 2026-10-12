"""Small real upstream stage tree used by the cancellation regression test."""
import sys

sys.path.insert(0, sys.argv[1])
from run_ddsurfer_pipeline import interruptible_run, wait_command

child = (
    "import os,time; from pathlib import Path; "
    f"Path({sys.argv[2]!r}).write_text(str(os.getpid())); "
    "print('STAGE_READY', flush=True); time.sleep(60)"
)
with interruptible_run():
    wait_command([sys.executable, '-c', child])
