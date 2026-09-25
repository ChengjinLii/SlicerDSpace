import os
import subprocess

from shared.external_process import startup_environment, text_subprocess_kwargs


def _mrtrix_seed_extra_env(PS):
    """Return an ``extra_env`` dict forwarding the MRtrix RNG seed, if any.

    ``startup_environment()`` uses ``slicer.util.startupEnvironment()``
    inside Slicer, which is a fixed snapshot captured at Slicer's own
    process launch time -- it does not reflect anything set on
    ``os.environ`` afterward. ``tractography/saf.py`` exports
    ``MRTRIX_RNG_SEED`` via ``os.environ`` (SAF runs in-process, not as a
    separate subprocess) for the duration of the SAF backend call; without
    explicitly forwarding it here via ``extra_env``, that seed would never
    reach the MRtrix commands this helper actually launches. ``PS`` (the
    SAF backend's own settings object) is checked too, for any caller that
    sets a seed there directly instead of via the environment.
    """

    seed = os.environ.get("MRTRIX_RNG_SEED") or getattr(PS, "random_seed", None)
    return {"MRTRIX_RNG_SEED": str(seed)} if seed is not None else None


def sys_exec(cmd, PS):
    """Run an external SAF command and stop immediately on failure."""

    extra_env = _mrtrix_seed_extra_env(PS)
    if getattr(PS, 'dgn', False):
        return subprocess.run(
            cmd,
            shell=True,
            check=True,
            env=startup_environment(extra_env=extra_env),
        )
    return subprocess.run(
        cmd,
        shell=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=startup_environment(extra_env=extra_env),
        **text_subprocess_kwargs(),
    )
