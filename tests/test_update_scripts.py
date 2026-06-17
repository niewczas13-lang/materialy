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
    assert "Repository not found" in text
    assert "repo jest prywatne" in text
