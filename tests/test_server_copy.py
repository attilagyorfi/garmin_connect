"""The Hungarian copy the server sends to the UI: rewording must not move an error to another branch,
weaken a warning or break a sentence that is put together from pieces."""
import importlib.util
import io
import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

import cloud_sync_job
import tips
from analytics import ReadinessResult, explainable_readiness, model_promotion_decision, red_flags, retraining_recommendation, training_decision
from cloud_sync_job import REAUTH_MARKERS, _authenticated_sync, _is_retryable_error, _new_job, _resume_failed_job, _schedule_retry, advance_sync
from garmin_sync import GarminSync, GarminSyncError

ROOT = Path(__file__).resolve().parents[1]
NO_KEY_OLD = "Nincs érvényes Garmin-munkamenet. Csatlakoztasd újra a fiókot a Beállításokban."


def needs_reauth(exc):
    return any(marker in str(exc).lower() for marker in REAUTH_MARKERS)


def decisions(exc):
    return _is_retryable_error(exc), needs_reauth(exc)


def with_cause(message, cause):
    exc = GarminSyncError(message)
    exc.__cause__ = cause
    return exc


def test_error_markers_are_unchanged():
    assert cloud_sync_job.RETRYABLE_MARKERS == (
        "429", "rate limit", "too many requests", "timeout", "timed out", "temporarily", "átmenetileg",
        "connection reset", "connection aborted", "connection error", "remote end closed",
        "service unavailable", "502", "503", "504",
    )
    assert REAUTH_MARKERS == ("hitelesítési hiba", "mfa szükséges")


# The old wording, the login failure behind it, and the retry / reconnect decision both wordings must give.
LOGIN_ERRORS = [
    ("Garmin rate limit. Várj, majd próbáld újra; az utolsó cache használható.", "429 Too Many Requests", (True, False)),
    ("Garmin rate limit. Várj, majd próbáld újra; az utolsó cache használható.", "RateLimit exceeded", (True, False)),
    ("A Garmin átmenetileg nem elérhető. Az eddigi szinkronizálási előrehaladás megmarad.", "Connection timed out", (True, False)),
    ("A Garmin átmenetileg nem elérhető. Az eddigi szinkronizálási előrehaladás megmarad.", "503 Service Unavailable", (True, False)),
    ("Garmin MFA szükséges. Csatlakoztasd újra a fiókot a Beállításokban.", "MFA challenge", (False, True)),
    ("Garmin hitelesítési hiba. Csatlakoztasd újra a fiókot a Beállításokban.", "invalid token", (False, True)),
]


@pytest.mark.parametrize(("old", "cause", "expected"), LOGIN_ERRORS)
def test_login_errors_keep_their_retry_and_reconnect_decision(monkeypatch, tmp_path, old, cause, expected):
    class FailingGarmin:
        def __init__(self, *_args, **_kwargs):
            pass

        @staticmethod
        def login(_tokenstore):
            raise RuntimeError(cause)

    monkeypatch.setattr("garmin_sync.Garmin", FailingGarmin)
    with pytest.raises(GarminSyncError) as caught:
        GarminSync(tmp_path, tokenstore="bundle").authenticate()
    new = caught.value
    assert str(new) != old
    assert decisions(new) == decisions(with_cause(old, new.__cause__)) == expected
    # The wording alone decides the same way, without help from the cause.
    assert decisions(GarminSyncError(str(new))) == decisions(GarminSyncError(old)) == expected

    marked = []
    monkeypatch.setattr(cloud_sync_job, "load_tokenstore", lambda user_id: "bundle")
    monkeypatch.setattr(cloud_sync_job, "mark_reauth_required", marked.append)
    with pytest.raises(GarminSyncError):
        _authenticated_sync("u1", "run")
    assert marked == (["u1"] if expected[1] else [])


def raise_missing_token_local(monkeypatch, tmp_path):
    GarminSync(tmp_path, use_environment=False).authenticate()


def raise_missing_token_cloud(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud_sync_job, "load_tokenstore", lambda user_id: "")
    _authenticated_sync("u1", "run")


def raise_unknown_list(monkeypatch, tmp_path):
    client = Mock()
    client.get_activities.return_value = {"unexpected": True}
    cloud_sync_job._advance_activities(_new_job(), Mock(client=client), Mock())


def raise_not_resumable(monkeypatch, tmp_path):
    _resume_failed_job({"status": "failed"})


def sync_lock_with(monkeypatch, db):
    lock = Mock()
    lock.__enter__ = lambda self: db
    lock.__exit__ = lambda self, *args: None
    monkeypatch.setattr(cloud_sync_job, "sync_lock", lambda user_id: lock)


def raise_locked(monkeypatch, tmp_path):
    sync_lock_with(monkeypatch, None)
    advance_sync("u1")


def raise_stale_run(monkeypatch, tmp_path):
    sync_lock_with(monkeypatch, object())
    monkeypatch.setattr(cloud_sync_job, "load_user_json", lambda *args: {"run_id": "newer"})
    advance_sync("u1", "older")


@pytest.mark.parametrize(("old", "trigger"), [
    (NO_KEY_OLD, raise_missing_token_local),
    (NO_KEY_OLD, raise_missing_token_cloud),
    ("A Garmin aktivitáslistája ismeretlen formátumban érkezett.", raise_unknown_list),
    ("Ez a szinkron nem folytatható. Indíts új szinkront.", raise_not_resumable),
    ("Már fut egy szinkronlépés. Rövidesen automatikusan újrapróbáljuk.", raise_locked),
    ("A szinkron munkamenete már nem érvényes. Indíts új szinkront.", raise_stale_run),
])
def test_final_errors_stay_final(monkeypatch, tmp_path, old, trigger):
    with pytest.raises(GarminSyncError) as caught:
        trigger(monkeypatch, tmp_path)
    assert str(caught.value) != old
    assert decisions(caught.value) == decisions(GarminSyncError(old)) == (False, False)


def test_exhausted_retries_message_is_final():
    job = _schedule_retry({**_new_job(), "phase": "wellness", "retry_count": cloud_sync_job.MAX_TRANSIENT_RETRIES})
    assert job["status"] == "failed" and "megmarad" in job["message"] and "folytathatod" in job["message"]
    assert decisions(GarminSyncError(job["message"])) == (False, False)


def test_same_error_has_the_same_wording_in_every_file():
    sources = {name: (ROOT / name).read_text(encoding="utf-8") for name in (
        "garmin_sync.py", "cloud_sync_job.py", "dashboard_api.py", "api/sync.py", "api/state.py", "api/dashboard.py",
        "api/model.py", "api/garmin.py", "api/assistant.py", "api/admin.py", "api/auth.py",
    )}
    for name in ("garmin_sync.py", "cloud_sync_job.py"):
        assert "Nincs érvényes Garmin-belépőkulcsod. Kösd össze újra a Garmint a Beállításokban." in sources[name]
    for name in ("cloud_sync_job.py", "dashboard_api.py", "api/sync.py"):
        assert "Váratlan hiba miatt megszakadt a szinkron. Próbáld újra pár perc múlva." in sources[name]
    for name in ("api/sync.py", "api/state.py", "api/dashboard.py", "api/model.py", "api/garmin.py", "api/assistant.py", "api/admin.py", "api/auth.py"):
        assert "Ehhez be kell jelentkezned." in sources[name]
        assert "bejelentkezés szükséges" not in sources[name]


def garmin_api():
    spec = importlib.util.spec_from_file_location("garmin_api_under_test", ROOT / "api" / "garmin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("message", "fragment"), [
    ("429 Client Error", "átmenetileg korlátozta"),
    ("rate exceeded", "átmenetileg korlátozta"),
    ("401 Unauthorized", "e-mail-címedet és a jelszavadat"),
    # Server texts that end up in the same text check; they stay verbatim, so they keep their branch.
    ("Az MFA-munkamenet nem állítható helyre. Indítsd újra a csatlakoztatást.", "kétlépcsős belépés (MFA)"),
    ("A Garmin-munkamenet nem fejthető vissza. Csatlakoztasd újra a fiókot.", "összekötni a Garmin-fiókodat"),
    ("Unexpected failure", "összekötni a Garmin-fiókodat"),
])
def test_garmin_connect_errors_keep_their_branch(monkeypatch, message, fragment):
    module = garmin_api()
    monkeypatch.setattr(module, "current_user", lambda headers: {"id": "u1"})
    monkeypatch.setattr(module, "load_mfa_state", Mock(side_effect=RuntimeError(message)))
    handler = object.__new__(module.handler)
    body = json.dumps({"action": "verify_mfa", "code": "123456"}).encode()
    handler.headers, handler.rfile, handler._send = {"Content-Length": str(len(body))}, io.BytesIO(body), Mock()
    handler.do_POST()
    payload, status = handler._send.call_args.args
    assert status == 502 and fragment in payload["error"]
    assert message not in payload["error"]  # no internal detail reaches the athlete


def test_mfa_runtime_errors_are_verbatim():
    source = (ROOT / "garmin_connection.py").read_text(encoding="utf-8")
    assert 'RuntimeError("Az MFA-munkamenet nem állítható helyre. Indítsd újra a csatlakoztatást.")' in source
    assert 'RuntimeError("A Garmin-munkamenet nem fejthető vissza. Csatlakoztasd újra a fiókot.")' in source


def frame(days=40, **columns):
    index = pd.date_range(end="2026-10-07", periods=days, freq="D")
    base = {"hrv": 60.0, "resting_hr": 50.0, "sleep_score": 85.0, "hybrid_load": 40.0, "hybrid_tsb": 2.0}
    return pd.DataFrame({key: value for key, value in {**base, **columns}.items()}, index=index)


def test_rationale_is_made_of_closed_sentences_with_unchanged_signals():
    result = explainable_readiness(frame(hrv=[60.0] * 39 + [30.0]))
    assert result.positives[:2] == ["Alvás: támogató", "RHR: támogató"]
    assert "HRV: korlátozó" in result.negatives
    rationale = training_decision(result, frame())["rationale"]
    assert rationale.startswith("Ma ez támogat: az alvásod és a nyugalmi pulzusod. Ma ez korlátoz: a HRV-d (")
    assert rationale.endswith(".") and ";" not in rationale


def test_rationale_knows_every_component_and_survives_without_signals():
    from analytics import RATIONALE_LABELS
    names = {"HRV", "Alvás", "RHR", "Terhelés / TSB", "Előző terhelés", "Manuális wellness"}
    assert set(RATIONALE_LABELS) == names
    assert {item["name"] for item in explainable_readiness(frame(), {"soreness": 1, "stress": 1, "fatigue": 1, "motivation": 3}).components} == names
    result = ReadinessResult(50, "magas", [], [], ["Manuális wellness: korlátozó", "Előző terhelés: korlátozó"], [])
    assert training_decision(result, frame())["rationale"] == "Ma ez korlátoz: a közérzeted a válaszaid alapján és az előző napok terhelése."
    empty = ReadinessResult(50, "magas", [], [], [], [])
    assert training_decision(empty, frame())["rationale"] == "A meglévő adataidat óvatosan értékeltük."


def test_flag_title_used_as_a_key_still_triggers_recovery():
    flags = red_flags(frame(hybrid_load=[10.0] * 37 + [90.0] * 3))
    assert "Három kemény nap egymás után" in {flag["title"] for flag in flags}
    result = ReadinessResult(75, "magas", [], [], [], [])
    assert training_decision(result, frame(), flags=flags)["rules"] == ["fatigue_recovery"]


def test_health_warnings_keep_their_strength():
    pulse = tips.resting_hr_tip(pd.DataFrame({"resting_hr": [50.0] * 37 + [57.0] * 3}))
    assert "kezdődő betegség jele is lehet" in pulse["action"] and "pihenő legyen" in pulse["action"]
    assert "kérd szakember tanácsát" in pulse["action"]
    hrv = tips.hrv_tip(pd.DataFrame({"hrv": [60.0] * 33 + [50.0] * 7}))
    assert "gyakran fáradtságot, stresszt vagy kevés alvást jelez" in hrv["message"]
    assert "ha betegnek érzed magad, pihenj" in hrv["action"].lower()
    assert "középső értéke (mediánja) 60 ms (-17%)" in hrv["why"]


def test_weekly_summary_reads_as_whole_sentences():
    rows = pd.DataFrame([
        {"date": pd.Timestamp("2026-09-29"), "duration_min": 60, "session_load": 1, "name": "Futás", "modality": "Cardio"},
        {"date": pd.Timestamp("2026-10-02"), "duration_min": 90, "session_load": 1, "name": "Erő", "modality": "Strength / Functional"},
        {"date": pd.Timestamp("2026-09-23"), "duration_min": 100, "session_load": 1, "name": "Túra", "modality": "Cardio"},
    ])
    today = date(2026, 10, 7)
    pulse = tips.resting_hr_tip(pd.DataFrame({"resting_hr": [50.0] * 37 + [57.0] * 3}))
    digest = tips.weekly_digest(frame(), rows, [pulse], today)
    assert digest["summary"].startswith("A múlt héten 2 edzésed volt, összesen 2,5 óra edzésidővel. Az edzésidőd +50% az előző héthez képest. A leghosszabb edzésed: Erő (90 perc).")
    assert digest["focus"] == pulse["action"] and digest["focus"].endswith(".")


def test_model_texts_are_unique_per_run_and_readable():
    active = {"active": True, "trained_at": "2026-01-01", "data_end": "2026-01-01", "model_mae": 0.4}
    reasons = retraining_recommendation([active], {"alerts": 2}, "2026-03-01", today="2026-03-01")["reasons"]
    assert len(reasons) == len(set(reasons)) == 3 and all(reason.endswith(".") for reason in reasons)
    texts = reasons + [
        model_promotion_decision({"status": "insufficient"}, [])["reason"],
        model_promotion_decision({"status": "validated", "eligible": True}, [])["reason"],
        model_promotion_decision({"status": "validated", "eligible": True, "model_mae": 0.3}, [active])["reason"],
        model_promotion_decision({"status": "validated", "eligible": True, "model_mae": 0.5}, [active])["reason"],
    ]
    assert "0.300 < 0.400" in texts[-2] and "0.400 ≤ 0.500" in texts[-1]
    for text in texts:
        assert not re.search(r"modelljelölt|címkézett|célértékes|drift|validáci|baseline", text)
