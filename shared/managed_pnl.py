"""Pinned upstream PNL assets and an isolated, author-compatible environment."""

from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import urllib.request

from shared.external_process import external_python_environment

PNL_COMMIT = "d7fe0fd4976c2d5a3489526f75d2a00dae3e1fe1"
CONVERSION_COMMIT = "cdd433adff3eebc486f2b5648714cbfe93b9422e"
PNL_TERMS_URL = "https://github.com/pnlbwh/CNN-Diffusion-MRIBrain-Segmentation"
PNL_MODEL_TERMS_URL = PNL_TERMS_URL + "/releases/tag/v0.3"
PNL_TEMPLATE_TERMS_URL = "https://www.nitrc.org/frs/?group_id=432"
ASSETS = {
    "pnl-source.tar.gz": (
        f"https://codeload.github.com/pnlbwh/CNN-Diffusion-MRIBrain-Segmentation/tar.gz/{PNL_COMMIT}",
        "b0737dc24dc5d0145c1819db7a5811777d673784c9ead48054f1724745624721"),
    "pnl-models.tar.gz": (
        "https://github.com/pnlbwh/CNN-Diffusion-MRIBrain-Segmentation/releases/download/v0.3/model_folder.tar.gz",
        "c67210fd59e5bcaf8e0e730bdde9d8f28b817148a74d9586a39c9b6e86df5191"),
    "IITmean_b0_256.nii.gz": (
        "https://www.nitrc.org/frs/download.php/11290/IITmean_b0_256.nii.gz",
        "2bb1a7bbe448702033a515e76164df6472828422ecef5cb4f996d91ec126dead"),
    "conversion.tar.gz": (
        f"https://codeload.github.com/pnlbwh/conversion/tar.gz/{CONVERSION_COMMIT}",
        "08e93b798cebd18ae7ea890db2912bd12ded94a3054992a97f9261f2d8d0be93"),
}
RESOURCE_HASHES = {
    "pnl-source/pipeline/dwi_masking.py": "de1180437804dcfdc6c4cdf697bed70c59ab8f5c196cc104be05519a1cb7d961",
    "pnl-source/LICENSE": "5525714ad257e12031974b608a7ee428f14ae28791c7ccbc0866271b24008d45",
    "pnl-models/CompNetBasicModel.json": "989fd5a64d9307268441c3525d59b31d59c20db864f0262ef53ad53ec495bdae",
    "pnl-models/IITmean_b0_256.nii.gz": ASSETS["IITmean_b0_256.nii.gz"][1],
    "pnl-models/weights-axial-improvement-08.h5": "e11d3c410769c68844109a86eed40ebedc655ea03c14f6f54f4f13749c5ead18",
    "pnl-models/weights-coronal-improvement-08.h5": "248dcf90752d4e0a2e22a136c5f0ca6d3c9cb9b628d131ce869d9ef6cbea702c",
    "pnl-models/weights-sagittal-improvement-09.h5": "27aaafddac65617e0653c4da4fd0c650529fcc8150b4efd6b66135070ebc01bc",
}


def pnl_python_environment(python, extra_env=None, path_prepend=()):
    """Expose only the selected Python's CUDA wheel libraries to its process."""
    import os
    prefix = Path(python).expanduser().absolute().parent.parent
    cuda_bins = sorted(prefix.glob("lib/python*/site-packages/nvidia/*/bin"))
    environment = external_python_environment(extra_env, path_prepend=[*path_prepend, prefix / "bin", *cuda_bins])
    libraries = [prefix / "lib", *sorted(prefix.glob("lib/python*/site-packages/nvidia/*/lib"))]
    paths = [str(path) for path in libraries if path.is_dir()]
    paths.extend(environment.get("LD_LIBRARY_PATH", "").split(os.pathsep))
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys(path for path in paths if path))
    return environment


def verified_download(name, cache):
    from shared.managed_runtimes import file_hash
    url, expected = ASSETS[name]
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if target.is_symlink():
        raise ValueError("Runtime download cannot be a symlink")
    if target.is_file() and file_hash(target) == expected:
        return target
    part = target.with_suffix(target.suffix + ".part")
    if part.is_symlink():
        raise ValueError("Runtime partial download cannot be a symlink")
    print("[PNL setup] Downloading " + name, flush=True)
    with urllib.request.urlopen(url, timeout=60) as source, part.open("wb") as destination:
        size = 0
        for block in iter(lambda: source.read(1024 * 1024), b""):
            destination.write(block)
            size += len(block)
            if size > 512 * 1024 * 1024:
                raise ValueError("PNL download exceeds its bounded size")
            print(f"[PNL setup] {name}: {size // (1024 * 1024)} MiB", flush=True)
    if file_hash(part) != expected:
        raise RuntimeError("PNL checksum mismatch: " + name)
    part.replace(target)
    return target


def extract_regular_files(archive, destination):
    """Drop the one archive root; reject links, traversal and oversized data."""
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("Runtime asset directory cannot be a symlink")
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if len(members) > 10000 or sum(item.size for item in members) > 1024**3:
            raise ValueError("Runtime archive exceeds extraction limits")
        roots = set()
        for item in members:
            path = PurePosixPath(item.name)
            if (not path.parts or path.is_absolute() or ".." in path.parts or "\\" in item.name
                    or ":" in item.name or not (item.isfile() or item.isdir())):
                raise ValueError("Unsafe runtime archive member: " + item.name)
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError("Runtime archive must have exactly one top-level folder")
        destination.mkdir(parents=True, exist_ok=True)
        for item in members:
            parts = PurePosixPath(item.name).parts[1:]
            if not parts or not item.isfile():
                continue
            target = destination.joinpath(*parts)
            if any(part.is_symlink() for part in (target, *target.parents)):
                raise ValueError("Refusing archive extraction through a symlink")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(item) as data, target.open("wb") as output:
                shutil.copyfileobj(data, output)


def provision_assets(prefix, cache, *, repair=False):
    from shared.managed_runtimes import _run
    archives = {name: verified_download(name, cache) for name in ASSETS}
    extract_regular_files(archives["pnl-source.tar.gz"], prefix / "pnl-source")
    extract_regular_files(archives["pnl-models.tar.gz"], prefix / "pnl-models")
    if (prefix / "pnl-models/IITmean_b0_256.nii.gz").is_symlink():
        raise ValueError("PNL template destination cannot be a symlink")
    shutil.copy2(archives["IITmean_b0_256.nii.gz"], prefix / "pnl-models/IITmean_b0_256.nii.gz")
    # TensorFlow 2.15/Keras 2 matches the reviewed author architecture. CUDA
    # libraries are user-local wheels; NVIDIA drivers are never installed.
    _run([str(prefix / "bin/python"), "-m", "pip", "install", *(["--force-reinstall"] if repair else []), "tensorflow[and-cuda]==2.15.1",
          "scikit-image==0.22.0", "numpy==1.26.4", "nibabel==5.2.1", "pynrrd==1.0.0",
          str(archives["conversion.tar.gz"])])


def verify_assets(prefix):
    from shared.managed_runtimes import file_hash
    source = prefix / "pnl-source"
    models = prefix / "pnl-models"
    required = [source / "pipeline/dwi_masking.py", source / "LICENSE",
                models / "CompNetBasicModel.json", models / "IITmean_b0_256.nii.gz"]
    for view in ("axial", "coronal", "sagittal"):
        weights = list(models.glob(f"weights-{view}-improvement-*.h5"))
        if len(weights) != 1:
            raise RuntimeError("PNL requires exactly one weight file per view")
        required.extend(weights)
    if any(not path.is_file() or path.is_symlink() for path in required):
        raise RuntimeError("PNL runtime resources are incomplete")
    for relative, expected in RESOURCE_HASHES.items():
        if file_hash(prefix / relative) != expected:
            raise RuntimeError("PNL resource checksum changed: " + relative)
    probe = Path(__file__).with_name("pnl_runtime_probe.py")
    subprocess.run([str(prefix / "bin/python"), str(probe), str(models)], check=True,
                   env=pnl_python_environment(prefix / "bin/python"), timeout=180)
    return {"external_dependencies": {"pnl_mask_python": str(prefix / "bin/python"),
            "pnl_mask_script": str(required[0]), "pnl_mask_model_dir": str(models),
            "pnl_mask_ants_bin_dir": str(prefix / "bin")},
            "pnl_resource_sha256": {str(path.relative_to(prefix)): file_hash(path) for path in required},
            "pnl_source_commit": PNL_COMMIT, "conversion_source_commit": CONVERSION_COMMIT}
