import subprocess

from shared.external_process import startup_environment


def sys_exec(cmd, PS):
    """Run an external SAF command and stop immediately on failure."""

    if getattr(PS, 'dgn', False):
        return subprocess.run(
            cmd,
            shell=True,
            check=True,
            env=startup_environment(),
        )
    return subprocess.run(
        cmd,
        shell=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=startup_environment(),
    )
