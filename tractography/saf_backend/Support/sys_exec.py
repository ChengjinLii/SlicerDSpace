import subprocess


def sys_exec(cmd, PS):
    if getattr(PS, 'dgn', False):
        subprocess.run(cmd, shell=True, check=False)
    else:
        subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
