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


def test_garmin_sync_prefers_serialized_tokens_over_token_dir(monkeypatch, tmp_path):
    import garmin_sync

    calls = []

    class FakeGarmin:
        def __init__(self, email, password):
            self.client = self

        def login(self, tokenstore):
            calls.append(tokenstore)

        def dumps(self):
            return '{"di_token": "x"}'

    monkeypatch.setattr(garmin_sync, "Garmin", FakeGarmin)
    sync = garmin_sync.GarminSync(tmp_path, email="a@example.com", password="titok", tokens='{"di_token": "x"}')
    sync.authenticate()
    assert calls == ['{"di_token": "x"}']
    assert sync.export_tokens() == '{"di_token": "x"}'
    garmin_sync.GarminSync(tmp_path, email="a@example.com", password="titok").authenticate()
    assert calls[-1] == str(tmp_path / ".garmin_tokens")
