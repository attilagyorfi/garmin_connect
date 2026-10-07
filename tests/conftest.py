import pytest


@pytest.fixture(autouse=True)
def _isolate_admin_bootstrap(monkeypatch):
    # dashboard_api loads .env.local at import; a developer's admin list must not leak into tests.
    monkeypatch.delenv("HYBRID_ADMIN_EMAILS", raising=False)
