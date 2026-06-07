import subprocess

from shared.external_process import startup_environment


def sys_exec(cmd, PS):
    if getattr(PS, 'dgn', False):
        subprocess.run(cmd, shell=True, check=False, env=startup_environment())
    else:
        subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=startup_environment())
