import pytest
import cloud_dashboard


def test_missing_snapshot_has_distinct_empty_state(monkeypatch):
    monkeypatch.setattr(cloud_dashboard, "load_user_json", lambda *_: None)
    with pytest.raises(cloud_dashboard.NoDashboardData):
        cloud_dashboard.dashboard_snapshot("test-user")


def test_storage_error_is_not_reported_as_empty_data(monkeypatch):
    def fail(*_):
        raise ConnectionError("storage unavailable")
    monkeypatch.setattr(cloud_dashboard, "load_user_json", fail)
    with pytest.raises(ConnectionError):
        cloud_dashboard.dashboard_snapshot("test-user")
