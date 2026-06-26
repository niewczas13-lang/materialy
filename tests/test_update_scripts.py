from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_update_batch_invokes_powershell_update_script():
    batch = ROOT / "AKTUALIZUJ_APKE.bat"

    assert batch.exists()
    text = batch.read_text(encoding="utf-8", errors="ignore")

    assert "scripts\\update_app.ps1" in text
    assert "ExecutionPolicy Bypass" in text


def test_update_script_stops_app_resets_from_git_and_starts_app_without_cleaning_inputs():
    script = ROOT / "scripts" / "update_app.ps1"

    assert script.exists()
    text = script.read_text(encoding="utf-8", errors="ignore")

    stop_pos = text.index("stop_app.ps1")
    fetch_pos = text.index("fetch --prune origin")
    reset_pos = text.index("reset --hard")
    start_pos = text.index("start_app.ps1")

    assert stop_pos < fetch_pos < reset_pos < start_pos
    assert "$TargetRef" in text
    assert "git clean" not in text.lower()
    assert "$LASTEXITCODE:" not in text
    assert "$PreviousErrorActionPreference" in text
    assert '$ErrorActionPreference = "Continue"' in text
    assert "Repository not found" in text
    assert "repo jest prywatne" in text


def test_autostart_scripts_register_and_remove_scheduled_task():
    add_batch = ROOT / "DODAJ_AUTOSTART.bat"
    remove_batch = ROOT / "USUN_AUTOSTART.bat"
    install_script = ROOT / "scripts" / "install_autostart.ps1"
    remove_script = ROOT / "scripts" / "remove_autostart.ps1"

    assert add_batch.exists()
    assert remove_batch.exists()
    assert install_script.exists()
    assert remove_script.exists()

    add_text = add_batch.read_text(encoding="utf-8", errors="ignore")
    remove_text = remove_batch.read_text(encoding="utf-8", errors="ignore")
    install_text = install_script.read_text(encoding="utf-8", errors="ignore")
    remove_script_text = remove_script.read_text(encoding="utf-8", errors="ignore")

    assert "scripts\\install_autostart.ps1" in add_text
    assert "scripts\\remove_autostart.ps1" in remove_text
    assert "FTTH BOM" in install_text
    assert "New-ScheduledTaskAction" in install_text
    assert "New-ScheduledTaskTrigger -AtLogOn" in install_text
    assert "Register-ScheduledTask" in install_text
    assert "start_app.ps1" in install_text
    assert "FTTH BOM" in remove_script_text
    assert "Unregister-ScheduledTask" in remove_script_text
