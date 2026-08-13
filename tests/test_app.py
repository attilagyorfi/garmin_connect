from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_app_renders(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    app = Path(__file__).parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Mai edzésdöntés"
    assert any("Readiness" in metric.label for metric in at.metric)
