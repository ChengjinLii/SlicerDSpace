"""Inspect plugin-owned WSL bridges without executing Windows binaries."""

from pathlib import Path


def bridge_config(executable):
    executable = Path(executable)
    marker = Path(str(executable) + ".slicerdsurfer-owner")
    if not marker.is_file():
        return None
    path = Path(str(executable) + ".conf")
    if not path.is_file():
        raise FileNotFoundError("WSL bridge configuration missing; rerun Windows runtime setup: " + str(path))
    fields, arguments = {}, []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError("Invalid WSL bridge configuration: " + str(path))
        key = key.strip().lower()
        if key == "arg":
            arguments.append(value)
        elif key in {"target", "distribution"}:
            fields[key] = value
    if not fields.get("distribution") or not fields.get("target", "").startswith("/"):
        raise ValueError("WSL bridge needs a distribution and absolute Linux target: " + str(path))
    return dict(fields, arguments=arguments)


def preprocessing_launcher(command, record_path, environment):
    """Run the same strict eddy policy in the actual Linux/WSL MRtrix Python."""
    import shutil

    script = Path(command[0])
    if script.name.lower() not in {"dwifslpreproc", "dwifslpreproc.exe"}:
        return command
    policy = Path(__file__).with_name("mrtrix_preproc_runner.py")
    config = bridge_config(script)
    if config is not None:
        python = script.parent / "python.exe"
        python_config = bridge_config(python)
        if not python.is_file() or python_config is None:
            raise FileNotFoundError("WSL MRtrix Python bridge missing; rerun scripts/install_deps_windows.ps1")
        if (python_config["distribution"] != config["distribution"]
                or python_config["target"] != config["target"]
                or len(config["arguments"]) != 1
                or not config["arguments"][0].startswith("/")
                or Path(config["arguments"][0]).name != "dwifslpreproc"
                or len(python_config["arguments"]) != 1
                or Path(python_config["arguments"][0]).parent != Path(config["arguments"][0]).parent
                or Path(python_config["arguments"][0]).name != "python"):
            raise ValueError("WSL MRtrix script/Python bridges must use the same distribution and runtime")
        target = config["arguments"][0]
    elif script.is_file() and "mrtrix3" in script.read_text(encoding="utf-8", errors="replace"):
        python = shutil.which("python", path=environment.get("PATH", ""))
        if not python:
            raise FileNotFoundError("The selected MRtrix external environment has no Python interpreter")
        target = str(script)
    elif script.suffix.lower() == ".exe":
        raise RuntimeError("Native Windows dwifslpreproc is not supported by this FSL route; configure the managed WSL bridges")
    else:
        return command
    return [str(python), str(policy), "--script", target, "--record", str(record_path), "--", *command[1:]]
