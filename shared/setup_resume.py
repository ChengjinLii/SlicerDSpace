"""Remember unfinished preparation, never commands or authorization to execute."""

import json
from pathlib import Path

KIND = "slicerddsurfer_pending_setup"


def pending_path():
    from shared.user_config import default_user_config_path

    return default_user_config_path().parent / "setup-history" / "pending.json"


def pending_setup():
    try:
        path = pending_path()
        if path.is_symlink():
            return None
        record = json.loads(path.read_text())
        token = record.get("request", "")
        if record.get("kind") != KIND or not token or token in {'.', '..'} or Path(token).name != token:
            return None
        return record
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def remember_setup(request):
    from shared.managed_runtimes import write_json

    if not request or request in {'.', '..'} or Path(request).name != request:
        raise ValueError("Invalid setup request identifier")
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"kind": KIND, "request": request, "status": "needs_preparation",
                      "policy": "Recheck current selections and ask confirmation; never resume scientific analysis automatically"})


def complete_setup(request):
    record = pending_setup()
    if record and record["request"] == request:
        pending_path().unlink(missing_ok=True)


def refresh_setup_button(owner):
    from shared.ui_onboarding import onboarding_text

    button = getattr(owner, "_managedRuntimeSetupButton", None)
    if button is None:
        return
    key = "managed_runtime_resume" if pending_setup() else "managed_runtime_setup"
    bindings = getattr(owner, "_uiLanguageBindings", [])
    owner._uiLanguageBindings = [(widget, prop, key if widget is button and prop == "text" else text)
                                 for widget, prop, text in bindings]
    button.setText(onboarding_text(getattr(owner, "_onboardingLanguage", "en"), key))
