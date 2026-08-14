from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_app_renders(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    app = Path(__file__).parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=20).run()
    assert not at.exception
    assert any("A mai döntés" in block.value for block in at.markdown)
    assert any("Mai ajánlott idő" in metric.label for metric in at.metric)


def test_all_hungarian_navigation_pages_render(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    app = Path(__file__).parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=20).run()
    for page in ["Terhelés és trendek", "Naptár", "Napló", "Egyensúly", "Hegyi felkészültség", "Mi működik nálam?", "Célok és tervek", "Heti jelentés", "Előzmények", "Beállítások és módszertan"]:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
