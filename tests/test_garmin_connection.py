import json

import pytest
from cryptography.fernet import Fernet

from garmin_connection import _cipher, _hint


def test_connection_cipher_round_trip(monkeypatch):
    monkeypatch.setenv("GARMIN_CREDENTIALS_KEY", Fernet.generate_key().decode())
    encrypted = _cipher().encrypt(json.dumps({"email": "a@example.com", "password": "titok"}).encode())
    assert b"titok" not in encrypted
    assert json.loads(_cipher().decrypt(encrypted))["password"] == "titok"


def test_missing_encryption_key_is_rejected(monkeypatch):
    monkeypatch.delenv("GARMIN_CREDENTIALS_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GARMIN_CREDENTIALS_KEY"):
        _cipher()


def test_email_hint_does_not_expose_full_address():
    hint = _hint("sportolo@example.com")
    assert hint.endswith("@example.com")
    assert "sportolo" not in hint
