from http.client import HTTPMessage

import pytest

from auth_store import _clean_credentials, _password_hash, _verify_password, cookie_header, token_from_headers


def test_scrypt_password_hash_is_salted_and_verifiable():
    first = _password_hash("hosszú-biztonságos-jelszó")
    second = _password_hash("hosszú-biztonságos-jelszó")
    assert first != second
    assert _verify_password("hosszú-biztonságos-jelszó", first)
    assert not _verify_password("hibás-jelszó", first)


@pytest.mark.parametrize("email,password", [
    ("hibás", "hosszú-biztonságos-jelszó"),
    ("sportolo@example.com", "rövid"),
])
def test_credentials_are_validated(email, password):
    with pytest.raises(ValueError):
        _clean_credentials(email, password)


def test_session_cookie_is_http_only_and_strict():
    value = cookie_header("titkos-token")
    assert "HttpOnly" in value
    assert "SameSite=Strict" in value
    assert "Secure" in value


def test_session_token_is_read_from_cookie_header():
    headers = HTTPMessage()
    headers.add_header("Cookie", "theme=teal; hybrid_session=session-token")
    assert token_from_headers(headers) == "session-token"
