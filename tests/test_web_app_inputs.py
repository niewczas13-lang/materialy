from pathlib import Path


def test_web_app_discovers_catalog_and_bell_dynamically(tmp_path, monkeypatch):
    import web_app

    monkeypatch.setattr(web_app, "INPUTS", tmp_path)

    missing = web_app.find_input_sources()
    assert missing.catalog is None
    assert missing.bell is None

    catalog = tmp_path / "KATALOGI PT_03_2026.xlsx"
    bell = tmp_path / "STAN BIEZACY _BELL_.xlsx"
    catalog.write_bytes(b"catalog")
    bell.write_bytes(b"bell")

    found = web_app.find_input_sources()

    assert found.catalog == catalog
    assert found.bell == bell
    status = web_app.render_input_status(found)
    assert str(tmp_path) in status
    assert "KATALOGI PT_03_2026.xlsx" in status
    assert "STAN BIEZACY _BELL_.xlsx" in status
