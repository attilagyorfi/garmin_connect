import pytest

from api.auth import _public_base_url, _validated_base_url


def test_configured_public_url_ignores_request_host(monkeypatch):
    monkeypatch.setenv("AUTH_PUBLIC_URL", "https://garmin-connect-six.vercel.app/")
    monkeypatch.delenv("VERCEL_PROJECT_PRODUCTION_URL", raising=False)
    monkeypatch.delenv("VERCEL_URL", raising=False)

    assert _public_base_url({
        "Host": "tamado.example",
        "X-Forwarded-Host": "tamado.example",
        "X-Forwarded-Proto": "https",
    }) == "https://garmin-connect-six.vercel.app"


def test_vercel_managed_url_is_used_without_request_host(monkeypatch):
    monkeypatch.delenv("AUTH_PUBLIC_URL", raising=False)
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "garmin-connect-six.vercel.app")

    assert _public_base_url({"Host": "tamado.example"}) == "https://garmin-connect-six.vercel.app"


def test_only_localhost_can_fall_back_to_request_host(monkeypatch):
    monkeypatch.delenv("AUTH_PUBLIC_URL", raising=False)
    monkeypatch.delenv("VERCEL_PROJECT_PRODUCTION_URL", raising=False)
    monkeypatch.delenv("VERCEL_URL", raising=False)

    assert _public_base_url({"Host": "127.0.0.1:4173", "X-Forwarded-Proto": "http"}) == "http://127.0.0.1:4173"
    with pytest.raises(RuntimeError, match="AUTH_PUBLIC_URL"):
        _public_base_url({"Host": "tamado.example", "X-Forwarded-Proto": "https"})


@pytest.mark.parametrize("url", [
    "http://example.com",
    "https://user:password@example.com",
    "https://example.com/reset",
    "https://example.com?redirect=https://tamado.example",
])
def test_public_url_rejects_unsafe_values(url):
    with pytest.raises(RuntimeError, match="biztonságosan"):
        _validated_base_url(url, allow_local_http=True)
