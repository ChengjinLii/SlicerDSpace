"""One explicit preparation action, with resumable phases and truthful status."""

from datetime import datetime
import json
from pathlib import Path


def python_setup_commands(owner, packages):
    """Group requests by their selected Python, never mix runtime targets."""
    import importlib.metadata
    import os
    import sys
    from shared.managed_runtimes import write_json
    from shared.user_config import default_user_config_path

    folder = Path(getattr(owner, "_latestEnvironmentReportDir", None) or default_user_config_path().parent / "setup-logs")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    script = Path(__file__).resolve().parents[1] / "scripts/setup_python_packages.py"
    groups = {}
    result = getattr(owner, "_lastEnvironmentResult", None)
    for package in packages:
        details = next(((item.details or {}) for item in getattr(result, "statuses", ())
                        if item.kind == "python" and package in {
                            (item.details or {}).get("package"), (item.details or {}).get("install_requirement")}), {})
        program, prefix = owner._setup_python_command(details.get("python_executable"))
        group = groups.setdefault((str(program), tuple(prefix)), {"requirements": [], "environment": {}})
        requirement = details.get("install_requirement") or package
        if requirement == "git+https://github.com/demianw/tract_querier.git":
            root = owner._environment_dependency_path_kwargs().get("tract_querier_root")
            if root and (Path(root) / "pyproject.toml").is_file():
                requirement = str(root)
                group["environment"]["SETUPTOOLS_SCM_PRETEND_VERSION_FOR_TRACT_QUERIER"] = "0+local"
        group["requirements"].append(requirement)
    loaded = {name for module, names in importlib.metadata.packages_distributions().items()
              if module in sys.modules for name in names}
    commands, receipts = [], []
    for index, ((program, prefix), data) in enumerate(groups.items()):
        slicer_python = bool(prefix) or Path(program).absolute() == Path(sys.executable).absolute()
        requirements = data["requirements"]
        if not slicer_python:
            from shared.external_process import external_python_environment
            clean = external_python_environment(path_prepend=[Path(program).parent])
            overrides = {key: None for key in os.environ if key not in clean}
            overrides.update(clean)
            overrides.update(data["environment"])
            data["environment"] = overrides
        torch_minimum = None
        torchvision_required = any(item == "torchvision" or item.startswith(("torchvision>", "torchvision=", "torchvision<"))
                                   for item in requirements)
        if slicer_python and (torchvision_required or any(item == "torch" or item.startswith(("torch>", "torch=", "torch<")) for item in requirements)):
            torch_minimum = "2.0.0"
            requirements = [item for item in requirements if not (item == "torch" or item.startswith(("torch>", "torch=", "torch<")))]
        request, receipt = (folder / f"python-{stamp}-{index}-{suffix}.json" for suffix in ("request", "result"))
        write_json(request, {"requirements": requirements, "torch_minimum": torch_minimum,
                            "torchvision_required": torchvision_required and slicer_python,
                            "protect_bundled": slicer_python, "loaded_packages": sorted(loaded) if slicer_python else [],
                            "python_path_entries": [path for path in sys.path if path] if slicer_python else []})
        commands.append((program, [*prefix, "-u", str(script), "--request", str(request), "--result", str(receipt)], data["environment"]))
        receipts.append(receipt)
    return commands, receipts


def _text(owner, english, chinese):
    return chinese if str(getattr(owner, "_onboardingLanguage", "en")).startswith("zh") else english


def _confirm(owner, plan):
    import qt
    import slicer
    from shared.managed_runtimes import FSL_TERMS_URL
    from shared.managed_pnl import PNL_TERMS_URL, PNL_MODEL_TERMS_URL, PNL_TEMPLATE_TERMS_URL

    dialog = qt.QDialog(slicer.util.mainWindow())
    dialog.setObjectName("selectedSetupConfirmationDialog")
    dialog.setWindowTitle(_text(owner, "Prepare selected analysis", "准备所选分析环境"))
    layout = qt.QVBoxLayout(dialog)
    parts = [_text(owner, "Only missing items for the selected analysis will be prepared. Existing installations are reused. No driver, shell or algorithm selection is changed.",
                   "仅准备当前分析缺少的依赖，复用已有安装；不修改驱动、shell 或算法选择。")]
    parts.append(_text(owner, "First-use downloads may require several GB and network access. Cancellation keeps completed files for retry.",
                       "首次下载可能需要数 GB 空间及网络连接；取消后保留已完成文件供重试。"))
    if plan.get("repair"):
        parts.append(_text(owner, "Repair will reinstall selected plugin-managed tools. Existing administrator environments are not changed.",
                           "修复将重新安装所选的插件受管工具，不修改管理员或自行配置的环境。"))
    for key in ("extensions", "restart_extensions", "python_packages", "asset_profiles", "managed_profiles", "unsupported_profiles"):
        if plan[key]:
            parts.append(key.replace("_", " ") + ": " + ", ".join(plan[key]))
    if plan["manual_items"]:
        parts.append(_text(owner, "Some items still need attention: ", "以下项目仍需处理：") +
                     ", ".join(item["label"] for item in plan["manual_items"]))
    if plan["pnl_terms_required"]:
        parts.append(_text(owner, "PNL source, model and template permissions are separate; download/hash verification is not a license grant.",
                           "PNL 源码、模型与模板的权限须分别核对；下载及哈希验证不代表获得授权。"))
    label = qt.QLabel("\n\n".join(parts))
    label.wordWrap = True
    layout.addWidget(label)
    approvals = []
    for required, url, caption in (
        (plan["fsl_license_required"], FSL_TERMS_URL, "FSL"),
        (plan["pnl_terms_required"], PNL_TERMS_URL, "PNL source, models and IIT template"),
    ):
        if required:
            link = qt.QLabel(f'<a href="{url}">{caption}</a>')
            link.openExternalLinks = True
            layout.addWidget(link)
            if caption.startswith("PNL"):
                assets = qt.QLabel(f'<a href="{PNL_MODEL_TERMS_URL}">PNL models</a> | '
                                  f'<a href="{PNL_TEMPLATE_TERMS_URL}">IIT template</a>')
                assets.openExternalLinks = True
                layout.addWidget(assets)
            check = qt.QCheckBox(_text(owner, "I have reviewed the terms and my use complies.", "我已阅读相关条款，且本次使用符合许可。"))
            approvals.append(check)
            layout.addWidget(check)
    buttons = qt.QDialogButtonBox(dialog)
    buttons.setStandardButtons(qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel)
    buttons.button(qt.QDialogButtonBox.Ok).setText(_text(owner, "Prepare", "开始准备"))
    buttons.button(qt.QDialogButtonBox.Ok).enabled = not approvals
    for check in approvals:
        check.connect("toggled(bool)", lambda *_: setattr(buttons.button(qt.QDialogButtonBox.Ok),
                                                          "enabled", all(item.checked for item in approvals)))
    buttons.connect("accepted()", dialog.accept)
    buttons.connect("rejected()", dialog.reject)
    layout.addWidget(buttons)
    accepted = dialog.exec_() == qt.QDialog.Accepted
    dialog.deleteLater()
    return accepted


def prepare_selected_environment(owner, result=None, *, repair=False):
    import slicer
    from shared.managed_runtimes import configured_profiles, cuda_candidate, selected_profiles, write_json
    from shared.selected_setup import build_setup_plan
    from shared.user_config import default_user_config_path

    if (getattr(owner, "_setupJob", None) or getattr(owner, "_pipelineActive", False)
            or getattr(owner, "_selectedSetupActive", False)):
        slicer.util.infoDisplay(_text(owner, "Wait for the active job or cancel it first.", "请先等待当前任务结束，或取消当前任务。"))
        return False
    result = result or owner._run_environment_dependency_check()
    if result is None:
        return False
    manager = slicer.app.extensionsManagerModel()
    installed = [name for name in ("SlicerDMRI", "PyTorch", "UKFTractography")
                 if manager and manager.isExtensionInstalled(name)]
    loaded = [name for name in installed if manager.isExtensionLoaded(name)]
    for name, module in (("SlicerDMRI", "dwitodtiestimation"), ("UKFTractography", "ukftractography")):
        if hasattr(slicer.modules, module):
            installed.append(name)
            loaded.append(name)
    targets = set(result.targets)
    gpu = cuda_candidate()
    candidates = list(selected_profiles(owner._parameterNode, gpu))
    if (getattr(owner._parameterNode, "brainMaskBackend", "pnl_cnn") == "pnl_cnn" and
            any(item.key == "brain_mask_backend" and item.required for item in result.statuses)):
        candidates.append("pnl_cnn")
    config = owner._environment_dependency_path_kwargs()
    existing = configured_profiles(config, candidates) if candidates else ()
    plan = build_setup_plan(result, installed_extensions=installed, loaded_extensions=loaded,
        need_dti=bool(targets & {"segmentation", "parcellation", "surface", "microstructure", "tractography"}),
        need_torch=bool(targets & {"segmentation", "parcellation", "surface"}),
        need_ukf="tractography" in targets and owner._tractography_backend_text() == "ukf",
        brain_mask_backend=getattr(owner._parameterNode, "brainMaskBackend", "pnl_cnn"), gpu_available=gpu,
        existing_managed_profiles=existing, repair=repair)
    if not _confirm(owner, plan):
        return False
    owner._selectedSetupActive = True
    folder = default_user_config_path().parent / "setup-history" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        owner._latestEnvironmentReportDir = folder
        write_json(folder / "plan.json", plan)
    except OSError as exc:
        owner._selectedSetupActive = False
        owner._setStatus("warning", str(exc))
        return False
    # Let Slicer's own manager select compatible extension builds. Installing
    # an extension does not make its modules available in the running session.
    for name in plan["extensions"]:
        try:
            success = manager is not None and manager.installExtensionFromServer(name, False)
        except Exception as exc:
            owner.appendLog("[Setup] Extension install failed: " + str(exc))
            success = False
        if not success:
            owner._selectedSetupActive = False
            owner._setStatus("warning", _text(owner, "Extension installation did not finish: ", "扩展安装未完成：") + name)
            write_json(folder / "result.json", {"status": "blocked", "extension": name})
            return False
    for name in plan["restart_extensions"]:
        try:
            manager.setExtensionEnabled(name, True)
        except Exception as exc:
            owner._selectedSetupActive = False
            write_json(folder / "result.json", {"status": "blocked", "extension": name, "error": str(exc)})
            owner._setStatus("warning", str(exc))
            return False
    if plan["extensions"] or plan["restart_extensions"]:
        owner._selectedSetupActive = False
        owner._setupRestartRequired = True
        owner._setStatus("warning", _text(owner, "Restart Slicer, then prepare the selected environment again.", "请重启 Slicer，再次准备所选分析环境以继续。"))
        write_json(folder / "result.json", {"status": "restart_required", "extensions": plan["extensions"] + plan["restart_extensions"]})
        slicer.util.infoDisplay(_text(owner, "Required extensions were installed. Save your work and restart Slicer; preparation will reuse them on retry.",
                                      "所需扩展已安装。请保存当前工作并重启 Slicer；再次准备时会复用这些扩展。"))
        return True

    def finish(status="completed", details=""):
        if status != "completed":
            owner._selectedSetupActive = False
            write_json(folder / "result.json", {"status": status, "details": details})
            owner._setStatus("warning", _text(owner, "Preparation stopped; inspect setup logs.", "环境准备已停止，请查看安装日志。"))
            return
        owner._selectedSetupActive = False
        try:
            current = owner._run_environment_dependency_check()
        except Exception as exc:
            write_json(folder / "result.json", {"status": "failed", "error": str(exc)})
            owner._setStatus("warning", str(exc))
            return
        pending = bool(getattr(owner, "_setupRestartRequired", False))
        state = "restart_required" if pending else "ready" if current and current.blocker_count == 0 else "blocked"
        write_json(folder / "result.json", {"status": state, "blockers": current.blocker_count if current else None,
                                            "scope": "Environment readiness only; not scientific QC"})
        if current:
            owner._update_environment_result_label(current)
            owner._update_environment_path_status_labels(current)
        owner._setStatus("ready" if state == "ready" else "warning", _text(owner,
            "Selected environment is ready." if state == "ready" else
            "Restart Slicer before analysis." if pending else "Preparation finished; some selected dependencies still need attention.",
            "所选分析环境已就绪。" if state == "ready" else
            "请重启 Slicer 后再运行分析。" if pending else "自动准备已结束，仍有依赖需要处理。"))
        if current and state == "blocked":
            owner._show_environment_results_dialog(current)

    def managed_setup():
        if not plan["managed_profiles"]:
            finish()
            return
        from shared.ui_setup_jobs import start_setup_job
        from shared.ui_managed_runtimes import apply_runtime_result
        script = Path(__file__).resolve().parents[1] / "scripts/setup_managed_runtime.py"
        receipt = folder / "runtime-result.json"
        args = ["--launch", "PythonSlicer", "-u", str(script), "--profiles", *plan["managed_profiles"],
                "--execute", "--result", str(receipt)]
        if plan["repair"]:
            args.append("--repair")
        if plan["fsl_license_required"]:
            args.append("--accept-fsl-license")
        if plan["pnl_terms_required"]:
            args.append("--accept-pnl-terms")
        conda = owner._environment_dependency_path_kwargs().get("conda_executable")
        if conda:
            args.extend(("--conda", str(conda)))

        def done(status, details, _log):
            if status == "completed":
                try:
                    apply_runtime_result(owner, json.loads(receipt.read_text()))
                except Exception as exc:
                    finish("failed", str(exc))
                    return
            finish(status, details)
        start_setup_job(owner, _text(owner, "Prepare external tools", "准备外部计算工具"),
                        [(owner._slicer_launcher_program(), args, {})], done)

    def model_setup(ok=True):
        if not ok:
            finish("failed", "Python setup did not complete")
        elif plan["asset_profiles"]:
            owner._install_model_assets_from_environment_dialog(profile=tuple(plan["asset_profiles"]),
                on_complete=lambda success, message: managed_setup() if success else finish("failed", message))
        else:
            managed_setup()

    try:
        if plan["python_packages"]:
            owner._install_python_packages_from_environment_dialog(tuple(plan["python_packages"]), on_complete=model_setup)
        else:
            model_setup()
    except Exception as exc:
        finish("failed", str(exc))
        return False
    return True


def use_offline_assets(owner):
    import qt
    import slicer
    from shared.user_config import default_user_config_path
    from shared.ui_setup_jobs import start_setup_job
    if (getattr(owner, "_setupJob", None) or getattr(owner, "_pipelineActive", False)
            or getattr(owner, "_selectedSetupActive", False)):
        return False
    selected = qt.QFileDialog.getExistingDirectory(slicer.util.mainWindow(),
        _text(owner, "Select an offline model resource directory", "选择离线模型资源目录"), str(Path.home()))
    if not selected:
        return False
    node = owner._parameterNode
    profiles = [name for name, target in (("surface", "targetSurface"), ("segmentation", "targetSegmentation"),
                                         ("parcellation", "targetParcellation")) if getattr(node, target, False)] or ["core"]
    receipt = default_user_config_path().parent / ("offline-assets-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parents[1] / "scripts/verify_offline_assets.py"
    args = ["--launch", "PythonSlicer", "-u", str(script), "--root", str(selected), "--profiles", *profiles,
            "--result", str(receipt)]

    def done(status, details, log):
        try:
            record = json.loads(receipt.read_text()) if receipt.is_file() else {}
        except (OSError, ValueError):
            record = {}
        if status == "completed" and record.get("status") == "completed":
            owner._save_environment_path_setting("model_assets_dir", record["root"])
            owner._environmentPathLineEdits["model_assets_dir"].setText(record["root"])
            owner._lastEnvironmentResult = owner._lastEnvironmentSignature = None
            owner._setStatus("ready", _text(owner, "Offline models verified; check remaining dependencies.", "离线模型已校验，请检查其余依赖。"))
        else:
            owner._setStatus("warning", _text(owner, "Offline verification failed; previous model path was preserved.", "离线校验未通过，原模型路径保持不变。"))
        owner.appendLog("[Setup] Offline asset verification: " + str(receipt))
    return start_setup_job(owner, _text(owner, "Verify offline models", "校验离线模型"),
                           [(owner._slicer_launcher_program(), args, {})], done)
