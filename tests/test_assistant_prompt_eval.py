"""The v5 prompt and its offline measuring tools: what may differ from the frozen v4, the v4/v5 pair, and the wording counters.
Nothing here may reach the network, create an Anthropic client or load a local settings file."""
import hashlib
import importlib
import json
import socket
import sys
import unicodedata
from types import ModuleType

import pytest

import assistant_prompts
from assistant_prompts import MEMORY_TASK, SUMMARY_TASK, SYSTEM_PROMPT
from evals.assistant.prompts import v4
from evals.assistant.wording import count_avoided_phrases, count_english_words

# sha256 of the string values in assistant_prompts.py on main (6c0e414), before v5.
MAIN_SHA256 = {
    "SYSTEM_PROMPT": "8bff5c564635843232f2355ae2db309c17fe17e6357788bed7e1a069081b4d3e",
    "SUMMARY_TASK": "9863d773c31bfd89f461fb49d3b486fb3a61713e79c0288c5640ec897476aba6",
    "MEMORY_TASK": "846191a8f8d114e01969fa3291879db4c13d3805ddf438f35e3379e0cce2a200",
}


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sections(prompt):
    """Introduction, the working rules, and the safety rules to the end."""
    assert prompt.count("Így dolgozz:") == 1 and prompt.count("Biztonság:") == 1
    start, safety = prompt.index("Így dolgozz:"), prompt.index("Biztonság:")
    return prompt[:start], prompt[start:safety], prompt[safety:]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("A teszt nem érhet el hálózatot, és nem hozhat létre Anthropic-klienst.")

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture(scope="module")
def run_eval():
    """The eval module, imported with a dotenv stub: run_eval and dashboard_api would both load local settings files."""
    requested = []
    stub = ModuleType("dotenv")
    stub.load_dotenv = lambda path=None, **_kwargs: requested.append(path)
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "dotenv", stub)
        patch.setattr(sys, "path", list(sys.path))
        patch.delitem(sys.modules, "evals.assistant.run_eval", raising=False)
        dashboard_was_loaded = "dashboard_api" in sys.modules
        module = importlib.import_module("evals.assistant.run_eval")
    # Every load request of the import chain went to the stub, so no file was read.
    assert module.load_dotenv is stub.load_dotenv
    assert len(requested) == (1 if dashboard_was_loaded else 3)
    return module


# ---------------------------------------------------------------- prompts

def test_v4_is_the_exact_main_prompt():
    assert sha256(v4.SYSTEM_PROMPT) == MAIN_SHA256["SYSTEM_PROMPT"]
    assert sha256(v4.SUMMARY_TASK) == MAIN_SHA256["SUMMARY_TASK"]


def test_only_the_working_rules_differ_from_v4():
    intro, rules, safety = sections(SYSTEM_PROMPT)
    v4_intro, v4_rules, v4_safety = sections(v4.SYSTEM_PROMPT)
    assert intro == v4_intro
    assert safety == v4_safety
    assert rules != v4_rules
    assert SUMMARY_TASK == v4.SUMMARY_TASK
    assert sha256(SUMMARY_TASK) == MAIN_SHA256["SUMMARY_TASK"]
    assert sha256(MEMORY_TASK) == MAIN_SHA256["MEMORY_TASK"]


def test_v5_is_at_most_five_percent_longer():
    assert len(SYSTEM_PROMPT) <= len(v4.SYSTEM_PROMPT) * 1.05


@pytest.mark.parametrize("rule", [
    "Úgy írj, mint egy jó edző: tegezve, rövid, hétköznapi mondatokban, cselekvő igékkel.",
    "Egy mondat egy gondolat.",
    "Kerüld a tölteléket, zsargont, gépies, hivatalos és szenvedő fordulatot.",
    "Magyarul válaszolj, angol szó nélkül: readiness helyett terhelhetőség, taper helyett visszaterhelés.",
    "A HRV, VO2max, Zone 2, RPE, TSB marad; ezeket és más szakszót első előforduláskor fél mondatban magyarázd meg.",
    "Ha a sportoló más nyelvet kér, írhatsz azon.",
    "a belső mezőneveit ne idézd",
])
def test_v5_language_rules(rule):
    assert rule in sections(SYSTEM_PROMPT)[1]


@pytest.mark.parametrize("rule", [
    "Csak a KONTEXTUS számaira és tényeire hivatkozz",
    "Ne találj ki adatot, és ne keverd az időszakokat (mai érték, heti átlag, 4 hetes alapszint).",
    "Ha egy szokásos mutató (VO2max, HRV, alvás, nyugalmi pulzus) hiányzik vagy „nincs adat”, félmondatban mondd ki, és javasold, honnan pótolja",
    "Az app motorja számol (terhelhetőség, terhelés, összevetések, jelzések).",
    "A motornak indoklás nélkül ne mondj ellent.",
    "általában 120–180 szót",
    "Ne hagyd ki, ami a döntéshez kell: mai helyzet, konkrét teendő, indok.",
    "Ha a sportoló rövid választ kér, vagy a MEMÓRIA szerint ezt szereti, legfeljebb 3–4 mondatot írj; ha részleteset kér, írhatsz többet.",
    "Ne használj emojit.",
    "Légy pozitív, motiváló, de őszinte: a gyenge pontot is mondd ki kíméletesen, a következő lépéssel.",
    "Vedd figyelembe a MEMÓRIA pontjait (preferenciák, panaszok, korábbi kérések); ha egy kérés ütközik velük, jelezd.",
    "„napok” és „tervek” mezőinek „nap” értékével nevezd meg, mezőnév nélkül; a hét napját ne te számold ki.",
    "Tervjavaslatot (propose_plan_change) csak akkor tegyél, ha a sportoló kifejezetten kéri egy edzés felvételét, módosítását, áthelyezését vagy törlését.",
    "Ha csak véleményt kér, értékeld a tervet, a módosítást legfeljebb ajánld fel.",
])
def test_v5_keeps_the_content_rules(rule):
    assert rule in sections(SYSTEM_PROMPT)[1]


# ---------------------------------------------------------------- the measured pair

def test_prompts_compare_frozen_v4_with_the_current_prompt(run_eval):
    [(old, new, kinds)] = run_eval.PROMPTS["comparisons"].values()
    assert kinds is None
    assert old == {"label": "v4", "model": "claude-sonnet-5-5", "system": v4.SYSTEM_PROMPT, "summary_task": v4.SUMMARY_TASK}
    assert new == {"label": "v5", "model": "claude-sonnet-5-5", "system": assistant_prompts.SYSTEM_PROMPT, "summary_task": assistant_prompts.SUMMARY_TASK}
    assert old["summary_task"] == new["summary_task"]
    assert run_eval.PROMPTS["judges"] == ["claude-opus-5-5"]


def test_earlier_prompts_stay_for_reference(run_eval):
    prompts = {run_eval.prompt_v1.SYSTEM_PROMPT, run_eval.prompt_v3.SYSTEM_PROMPT, v4.SYSTEM_PROMPT, SYSTEM_PROMPT}
    assert len(prompts) == 4


def test_prompts_dry_run_only_prints_an_estimate(run_eval, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_eval.py", "--prompts", "--dry-run"])
    run_eval.main()
    output = capsys.readouterr().out
    assert "36 eset" in output and "Becsült költség" in output


# ---------------------------------------------------------------- wording counters

@pytest.mark.parametrize(("text", "expected"), [
    ("A mai readiness 78.", 1),
    ("READINESS, Readiness és readiness", 3),
    ("A readiness-ed jó, a readinessed is.", 2),
    ("A taperelés előtt jön a taper.", 2),
    ("Az Insights oldalon két workoutot találsz, a recoverydre figyelj.", 3),
    ("A „readiness_összetevők” és a mai_readiness mező", 2),
    ("**Recovery** nap, cool-down és warm-up", 3),
    ("A HRV (pulzusszórás), a VO2max, a Zone 2, az RPE és a TSB rendben.", 0),
    ("Terhelhetőség, visszaterhelés, check-in, tempó, fartlek, intervall.", 0),
    ("Az éreadiness és az étaper nem szó eleje.", 0),
    ("", 0),
])
def test_english_words_are_counted(text, expected):
    assert count_english_words(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("Fontos, hogy pihenj. Nagyon fontos, hogy aludj.", 2),
    ("FONTOS, HOGY", 1),
    ("**Fontos**, hogy pihenj.", 1),
    ("fontos,   hogy", 1),
    ("fontos,\n  hogy", 1),
    ("Az ÁTFOGÓAN közérthetőbb kép", 2),
    ("Érdemes\tmegjegyezni, ez  azt\njelenti, hogy jól vagy.", 2),
    ("Egy helyen látod, egy pillantással.", 2),
    ("A személyre szabott élményt figyelembe vesszük.", 2),
    ("Lehetővé teszik, és segít abban, hogy fuss.", 2),
    ("Ez alapként funkcionál, a TSB-ként funkcionáló érték is.", 2),
    ("A legfontosabb, hogy pihenj. Fontos, hogyan futsz.", 0),
    ("Ez mindenátfogó, négy helyen.", 0),
    ("Ma fuss könnyen 40 percet.", 0),
    ("", 0),
])
def test_avoided_phrases_are_counted(text, expected):
    assert count_avoided_phrases(text) == expected


def test_decomposed_accents_are_counted():
    assert count_avoided_phrases(unicodedata.normalize("NFD", "Átfogó kép. Érdemes megjegyezni.")) == 2


def test_the_two_counters_are_separate():
    text = "Fontos, hogy a readiness jó."
    assert (count_english_words(text), count_avoided_phrases(text)) == (1, 1)


def row(case_id, v4_answer, v5_answer):
    return {"comparison": "Prompt v4 vs v5 (Sonnet 5.5)", "models": ["v4", "v5"], "case": {"id": case_id, "category": "kérdés"},
            "answers": {"v4": v4_answer, "v5": v5_answer}, "verdicts": {}}


def test_report_shows_both_counters_for_both_variants(run_eval):
    rows = [
        row("Q1", {"text": "Fontos, hogy a readiness jó. Readiness: 78."}, {"text": "A terhelhetőséged 78 pont."}),
        row("S1", {"text": "Átfogóan: taper."}, {"text": "Közérthető workout, insight."}),
        # English on request: neither counter looks at it.
        row("Q10", {"text": "Your readiness and recovery are fine, átfogó."}, {"text": "Your workout is easy."}),
        # A failed answer has no text.
        row("Q2", {"error": "APIStatusError: túlterhelt", "latency": 1.0}, {"text": "Fontos, hogy aludj."}),
    ]
    lines = run_eval.report(rows, 0.0, run_eval.PROMPTS).splitlines()
    assert "| Angol szó a magyar válaszokban | 3 | 2 |" in lines
    assert "| Kerülendő fordulat a magyar válaszokban | 2 | 2 |" in lines


def test_only_the_english_case_is_skipped(run_eval):
    cases = json.loads((run_eval.HERE / "cases.json").read_text(encoding="utf-8"))
    assert run_eval.NON_HUNGARIAN_CASES == {"Q10"}
    assert [case["id"] for case in cases if "in English" in case.get("question", "")] == ["Q10"]


def test_failed_or_empty_answers_count_as_zero(run_eval):
    rows = [row("Q1", {"error": "hiba"}, {"error": "hiba", "text": "readiness"}), row("Q2", {}, {"text": None})]
    for label in ("v4", "v5"):
        assert run_eval.wording_total(rows, label, count_english_words) == 0
        assert run_eval.wording_total(rows, label, count_avoided_phrases) == 0
