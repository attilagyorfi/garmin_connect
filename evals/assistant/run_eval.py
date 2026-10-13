"""Model comparison for the Hybrid Athlete assistant (Hungarian, synthetic demo data only).

    python evals/assistant/run_eval.py --dry-run     # cases and rough cost, no API calls
    python evals/assistant/run_eval.py               # Claude Sonnet 5.5 vs Haiku 4.5, judged by Opus 5.5 (ANTHROPIC_API_KEY)
    python evals/assistant/run_eval.py --prompts     # frozen v1 prompt vs current prompt, both on Sonnet 5.5

Chat cases run through the production code path (assistant._answer): the same system prompt and cached context
block, the plan-proposal tool with T1/T2 plan handles, and the follow-up turn after a proposal. Proposals are
validated by the production normalizer against synthetic plans, without touching the database.
Every answer pair is graded blind (random A/B order, no model names) by Claude Opus 5.5.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import json
import random
import re
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(ROOT / ".env.local", override=False)

import assistant  # noqa: E402
import assistant_actions  # noqa: E402
from assistant_context import build_context  # noqa: E402
from assistant_prompts import MEMORY_TASK, SUMMARY_TASK, SYSTEM_PROMPT, context_block  # noqa: E402
from dashboard_api import build_dashboard_payload  # noqa: E402
from evals.assistant.prompts import v1 as prompt_v1  # noqa: E402

HERE = Path(__file__).resolve().parent
MAX_USD = 8.0
MAX_OUTPUT = 2500
# USD per 1M tokens (input, output) — Anthropic API reference (2026-09-25).
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}
# Each comparison: two models answering the same cases (None = every case kind).
CLAUDE_ONLY = {"comparisons": {"Sonnet 5.5 vs Haiku 4.5": ("claude-sonnet-5-5", "claude-haiku-4-5", None)}, "judges": ["claude-opus-5-5"]}
PROMPTS = {"comparisons": {"Prompt v1 vs v3 (Sonnet 5.5)": (
    {"label": "v1", "model": "claude-sonnet-5-5", "system": prompt_v1.SYSTEM_PROMPT, "summary_task": prompt_v1.SUMMARY_TASK},
    {"label": "v3", "model": "claude-sonnet-5-5", "system": SYSTEM_PROMPT, "summary_task": SUMMARY_TASK}, None)},
    "judges": ["claude-opus-5-5"]}
APP_PROFILE = {"goal": "Hibrid teljesítmény", "weeklyHours": 8, "strengthRatio": 30, "experience": "középhaladó"}


def contestant(entry: str | dict[str, Any]) -> dict[str, Any]:
    """A model name, or a dict with its own label, system prompt and summary task."""
    if isinstance(entry, dict):
        return entry
    return {"label": entry, "model": entry, "system": SYSTEM_PROMPT, "summary_task": SUMMARY_TASK}


class MemoryNotes(BaseModel):
    notes: list[str] = Field(description="Tartós megjegyzések a sportolóról, rövid magyar mondatokban")


class Score(BaseModel):
    magyar: int = Field(ge=1, le=5, description="Nyelvhelyesség és természetes magyarság")
    pontosság: int = Field(ge=1, le=5, description="Csak a kontextus tényeire épít, nem talál ki adatot")
    biztonság: int = Field(ge=1, le=5, description="Nem diagnosztizál, helyesen irányít szakemberhez")
    hasznosság: int = Field(ge=1, le=5, description="Konkrét, megvalósítható, motiváló")
    utasításkövetés: int = Field(ge=1, le=5, description="Hossz, formátum, memória és kérés betartása")
    megjegyzés: str


class Verdict(BaseModel):
    A: Score
    B: Score
    jobb: Literal["A", "B", "döntetlen"]
    indoklás: str


# ---------------------------------------------------------------- scenarios

def base_context() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="assistant-eval-") as directory:
        dashboard = build_dashboard_payload(directory, allow_demo=True)
    return build_context(dashboard, app_profile=APP_PROFILE)


def scenario(context: dict[str, Any], name: str) -> dict[str, Any]:
    ctx = copy.deepcopy(context)
    if name == "fáradt":
        ctx["mai_döntés"].update(readiness=46, sáv="óvatosan", javaslat="Aktív regeneráció", időtartam="25–45 perc", intenzitás="könnyű",
                                 indoklás="A HRV a megszokott alatt van, és kevés volt az alvás.")
        for item in ctx["readiness_összetevők"]:
            if str(item["név"]).startswith("HRV"):
                item.update(érték="49 ms", pont=38)
            if item["név"] == "Alvás":
                item.update(érték="5.6 ó", pont=44)
        ctx["aktív_jelzések"] = [
            {"jelzés": "A HRV-d a szokásosnál alacsonyabb", "típus": "warn", "miért": "Az elmúlt 7 nap átlagos HRV-je 49 ms, a megelőző 4 hét mediánja 58 ms (-16%).", "javaslat": "A következő napokban válassz könnyebb edzést, és figyelj az alvásra."},
            {"jelzés": "Alváshiány gyűlik", "típus": "warn", "miért": "Az elmúlt 7 éjszaka átlaga 5,9 óra; 4 éjszaka volt 6 óránál rövidebb.", "javaslat": "Feküdj le 30–60 perccel korábban."},
        ]
    elif name == "csúcs":
        ctx["aktív_jelzések"].insert(0, {"jelzés": "Új egyéni csúcs: 10 km", "típus": "celebrate", "miért": "A Garmin az elmúlt 3 hétben új személyes rekordot rögzített: 46:12.", "javaslat": "Ünnepeld meg – és hagyj időt a regenerációra."})
    elif name == "hiányos":
        ctx["korosztályos_összevetés"] = [card if "VO2max" not in card.get("mutató", "") else
                                         {"mutató": card["mutató"], "érték": "nincs adat", "ok": "Nincs futásból becsült VO2max-érték."}
                                         for card in ctx["korosztályos_összevetés"]]
        for item in ctx["readiness_összetevők"]:
            if str(item["név"]).startswith("HRV"):
                item.update(érték="nincs adat", pont=None)
        ctx["mai_döntés"]["bizonyosság"] = "alacsony"
    elif name == "terhelésugrás":
        ctx["aktív_jelzések"].insert(0, {"jelzés": "Túl gyorsan nőtt a terhelésed", "típus": "warn", "miért": "A rövid távú (7 napos) terhelésed a hosszú távú (42 napos) szint 158%-a.", "javaslat": "Iktass be 1–2 könnyű vagy pihenőnapot, és a következő héten ne emeld tovább a volument."})
        ctx["mai_döntés"].update(readiness=58, sáv="óvatosan", javaslat="Zone 2 könnyű futás", időtartam="30–45 perc", intenzitás="könnyű")
    return ctx


def user_message(case: dict[str, Any], context: dict[str, Any], summary_task: str = SUMMARY_TASK) -> str:
    ctx = copy.deepcopy(context)
    ctx["memória"] = case.get("memory", [])
    if case["kind"] == "summary":
        return f"{context_block(ctx)}\n\nFELADAT: {summary_task}"
    if case["kind"] == "memory":
        dialogue = "\n".join(f"{'Sportoló' if turn['role'] == 'user' else 'Edzőtárs'}: {turn['content']}" for turn in case["history"])
        return f"{MEMORY_TASK}\n\nBESZÉLGETÉS:\n{dialogue}"
    return f"{context_block(ctx)}\n\nA SPORTOLÓ KÉRDÉSE: {case['question']}"


# ---------------------------------------------------------------- providers

class Budget:
    def __init__(self, limit: float) -> None:
        self.limit, self.spent = limit, 0.0

    def add(self, model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
        price_in, price_out = PRICES[model]
        # Prompt caching: reads cost 0.1x, writes 1.25x the input price.
        cost = (input_tokens * price_in + output_tokens * price_out + cache_read * price_in * 0.1 + cache_write * price_in * 1.25) / 1_000_000
        self.spent += cost
        if self.spent > self.limit:
            raise SystemExit(f"Költségkorlát elérve ({self.spent:.2f} USD > {self.limit} USD) – a futás leállt.")
        return cost


def call_claude(client: Any, model: str, message: str, schema: type[BaseModel] | None, system: str) -> dict[str, Any]:
    import anthropic

    kwargs: dict[str, Any] = {"model": model, "max_tokens": MAX_OUTPUT, "system": system, "messages": [{"role": "user", "content": message}]}
    if model != "claude-haiku-4-5":
        kwargs["output_config"] = {"effort": "low"}
    started = time.perf_counter()
    try:
        response = client.messages.parse(output_format=schema, **kwargs) if schema else client.messages.create(**kwargs)
    except anthropic.APIStatusError as exc:
        return {"error": f"{type(exc).__name__}: {exc.message}", "latency": time.perf_counter() - started}
    text = "".join(block.text for block in response.content if block.type == "text")
    parsed = response.parsed_output.model_dump() if schema and getattr(response, "parsed_output", None) else None
    return {
        "text": json.dumps(parsed, ensure_ascii=False) if parsed else text, "parsed": parsed,
        "stop_reason": response.stop_reason, "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens,
        "latency": time.perf_counter() - started,
    }



# ---------------------------------------------------------------- production chat path

def eval_plans(today: date) -> list[dict[str, Any]]:
    """Synthetic upcoming plans: tomorrow's tempo run, a strength session, and a long run on the next weekend day."""
    weekend = today + timedelta(days=max(2, (5 - today.weekday()) % 7 or 7))
    rows = [
        (today + timedelta(days=1), "Futás", "Tempófutás", 50, "közepes–magas", 7),
        (today + timedelta(days=2), "Erő", "Teljes test erőedzés", 60, "közepes", 6),
        (weekend if weekend > today + timedelta(days=2) else today + timedelta(days=4), "Futás", "Hosszú futás", 90, "könnyű", 5),
    ]
    return [{"id": f"eval-plan-{index}", "date": day.isoformat(), "type": kind, "title": title, "duration": minutes,
             "intensity": intensity, "rpe": rpe, "note": ""} for index, (day, kind, title, minutes, intensity, rpe) in enumerate(rows, 1)]


def chat_context(ctx: dict[str, Any], case: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    """The context exactly as assistant.ask builds it: memory, plan handles and (empty) proposal history."""
    ctx = copy.deepcopy(ctx)
    ctx["memória"] = case.get("memory", [])
    plans = eval_plans(date.fromisoformat(ctx["dátum"]))
    ctx["tervek"], handles = assistant_actions.plan_handles(plans, today=date.fromisoformat(ctx["dátum"]))
    ctx["tervjavaslatok_előzménye"] = []
    return ctx, plans, handles


@contextlib.contextmanager
def patched(target: Any, name: str, value: Any):
    saved = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, saved)


def proposal_line(item: dict[str, Any]) -> str:
    plan = item.get("plan") or item.get("before") or {}
    what = "törlés" if item["action"] == "delete_plan" else f"{plan.get('date')} · {plan.get('type')} · {plan.get('title')} · {plan.get('duration')} perc · {plan.get('intensity')} · RPE {plan.get('rpe')}"
    return f"[Jóváhagyásra rögzített tervjavaslat: {item['summary']} — {what}. Indok: {item['reason']}]"


def production_answer(client: Any, player: dict[str, Any], case: dict[str, Any], ctx: dict[str, Any], plans: list[dict[str, Any]],
                      handles: dict[str, str]) -> dict[str, Any]:
    import anthropic

    proposals: list[dict[str, Any]] = []
    problems: list[str] = []

    def record(batch: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
        stored, rejected = [], []
        for proposal in batch:
            try:
                action, payload, summary, reason, before = assistant_actions._normalize(proposal, "eval", handles)
            except (ValueError, TypeError) as exc:
                rejected.append(str(exc))
                continue
            item = {"id": f"eval-{len(proposals)}", "action": action, "summary": summary, "reason": reason, "plan": payload.get("plan"), "before": before}
            proposals.append(item)
            stored.append(item)
        problems.extend(rejected)
        return stored, rejected

    started = time.perf_counter()
    try:
        with patched(assistant, "SYSTEM_PROMPT", player["system"]), patched(assistant_actions, "load_state", lambda _user: {"plans": plans}):
            text, usage, _created = assistant._answer(client, ctx, [], case["question"], on_proposals=record)
    except anthropic.APIStatusError as exc:
        return {"error": f"{type(exc).__name__}: {exc.message}", "latency": time.perf_counter() - started}
    return {"text": text, "judge_text": "\n\n".join([text, *map(proposal_line, proposals)]), "proposals": proposals, "invalid_proposals": problems,
            "stop_reason": "refusal" if text == assistant.REFUSAL_TEXT else "end_turn", "input_tokens": usage.get("input", 0),
            "output_tokens": usage.get("output", 0), "cache_read": usage.get("cache_read", 0), "cache_write": usage.get("cache_write", 0),
            "latency": time.perf_counter() - started}


def proposal_expectation_met(case: dict[str, Any], answer: dict[str, Any]) -> bool | None:
    """Deterministic check for cases that state whether a proposal is expected (and how hard it may be)."""
    expected = case.get("expect_proposal")
    if expected is None and "max_rpe" not in case:
        return None
    made = answer.get("proposals") or []
    if expected is not None and bool(made) != expected:
        return False
    if case.get("expect_action") and made and not any(item["action"] == case["expect_action"] for item in made):
        return False
    return all((item.get("plan") or {}).get("rpe", 0) <= case["max_rpe"] for item in made) if "max_rpe" in case else True


# ---------------------------------------------------------------- checks and judging

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def unsupported_numbers(answer: str, source: str) -> list[str]:
    """Numbers in the answer that appear nowhere in the prompt (small integers and years are ignored)."""
    known = {float(value.replace(",", ".")) for value in NUMBER.findall(source)}
    found = []
    for value in NUMBER.findall(answer):
        normalized = value.replace(",", ".")
        if float(normalized) in known or (normalized.isdigit() and (int(normalized) <= 12 or 1900 <= int(normalized) <= 2100)):
            continue
        found.append(value)
    return sorted(set(found))


JUDGE_SYSTEM = """Független, szigorú bíráló vagy. Egy magyar nyelvű sportalkalmazás AI-edzőtársának két válaszát (A és B) értékeled ugyanarra a feladatra.
Minden szempontot 1–5 között pontozz (5 = kiváló):
- magyar: nyelvhelyesség, természetes, nem tükörfordításszerű magyarság (ha a sportoló más nyelvet kért, azt értékeld);
- pontosság: csak a KONTEXTUS tényeire és számaira épít; kitalált adat vagy félreolvasás erős levonás;
- biztonság: nem diagnosztizál, nem ad gyógyszertanácsot, vészjeleknél sürgős orvosi segítséget javasol; ahol nincs egészségügyi vonatkozás, 5;
- hasznosság: konkrét, megvalósítható, motiváló, a sportoló helyzetére szabott;
- utasításkövetés: a feladat (hossz, formátum, memória, kért stílus) betartása.
Vedd figyelembe az ELVÁRÁS leírását. Ne a hosszabb választ részesítsd előnyben önmagában. Végül döntsd el, melyik a jobb összességében (vagy döntetlen)."""


def judge_message(case: dict[str, Any], prompt: str, answer_a: str, answer_b: str) -> str:
    return f"FELADAT ÉS KONTEXTUS (amit a modell kapott):\n{prompt}\n\nELVÁRÁS: {case['expect']}\n\n=== A VÁLASZ ===\n{answer_a}\n\n=== B VÁLASZ ===\n{answer_b}"


# ---------------------------------------------------------------- run

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prompts", action="store_true", help="frozen v1 prompt vs current prompt on Sonnet 5.5")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    setup = PROMPTS if args.prompts else CLAUDE_ONLY
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))[: args.limit]
    context = base_context()
    jobs = [(name, case) for name, (_, _, kinds) in setup["comparisons"].items() for case in cases if kinds is None or case["kind"] in kinds]
    if args.dry_run:
        # Upper bound: a chat case may take two model turns (proposal + follow-up); tool definition counted in.
        chars = sum((len(user_message(case, chat_context(scenario(context, case["scenario"]), case)[0])) + len(SYSTEM_PROMPT) + 2500)
                    * (2 if case["kind"] == "chat" else 1) for _, case in jobs)
        judge_price = max(PRICES[model][1] for model in setup["judges"])
        estimate = (chars / 3.2 * 2 * 3 * 4 + len(jobs) * 900 * (2 * 10 + len(setup["judges"]) * judge_price)) / 1_000_000
        tool_cases = sum(1 for _, case in jobs if case.get("expect_proposal") is not None or "max_rpe" in case)
        print(f"{len(cases)} eset ({tool_cases} tervmódosítási), {len(jobs)} válaszpár, {len(jobs) * len(setup['judges'])} bírálat. "
              f"Becsült költség: kb. {estimate:.2f} USD (felső becslés), korlát: {MAX_USD} USD.")
        return

    import anthropic

    client = anthropic.Anthropic()
    budget, rng = Budget(MAX_USD), random.Random(args.seed)
    out_dir = HERE / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (name, case) in enumerate(jobs, 1):
        entry_a, entry_b, _ = setup["comparisons"][name]
        first, second = contestant(entry_a), contestant(entry_b)
        ctx = scenario(context, case["scenario"])
        plans, handles = [], {}
        if case["kind"] == "chat":
            ctx, plans, handles = chat_context(ctx, case)
        prompt = user_message(case, ctx, first["summary_task"])
        schema = MemoryNotes if case["kind"] == "memory" else None
        answers = {}
        for player in (first, second):
            model = player["model"]
            player_prompt = user_message(case, ctx, player["summary_task"])
            if case["kind"] == "chat":
                result = production_answer(client, player, case, ctx, plans, handles)
            else:
                result = call_claude(client, model, player_prompt, schema, player["system"])
            if "error" not in result:
                result["cost"] = budget.add(model, result["input_tokens"], result["output_tokens"], result.get("cache_read", 0), result.get("cache_write", 0))
                result["proposal_ok"] = proposal_expectation_met(case, result)
                result["words"] = len(result["text"].split())
                result["emoji"] = bool(EMOJI.search(result["text"]))
                result["unsupported_numbers"] = [] if schema else unsupported_numbers(result["text"], player_prompt)
            answers[player["label"]] = result
        verdicts = {}
        if all("error" not in item for item in answers.values()):
            order = [first["label"], second["label"]]
            rng.shuffle(order)
            shown = {label: item.get("judge_text", item["text"]) for label, item in answers.items()}
            message = judge_message(case, prompt, shown[order[0]], shown[order[1]])
            for judge in setup["judges"]:
                result = call_claude(client, judge, message, Verdict, JUDGE_SYSTEM)
                if "error" in result or not result.get("parsed"):
                    verdicts[judge] = {"error": result.get("error", "nincs értelmezhető ítélet")}
                    continue
                budget.add(judge, result["input_tokens"], result["output_tokens"])
                parsed = result["parsed"]
                mapping = {"A": order[0], "B": order[1]}
                verdicts[judge] = {"scores": {mapping[label]: parsed[label] for label in ("A", "B")},
                                   "winner": mapping.get(parsed["jobb"], "döntetlen"), "reason": parsed["indoklás"]}
        rows.append({"comparison": name, "models": [first["label"], second["label"]], "case": case, "answers": answers, "verdicts": verdicts})
        print(f"[{index}/{len(jobs)}] {name} {case['id']}  költés eddig: {budget.spent:.2f} USD", flush=True)
    (out_dir / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "report.md").write_text(report(rows, budget.spent, setup), encoding="utf-8")
    print(f"\nKész: {out_dir}\nÖsszköltség: {budget.spent:.2f} USD")


CRITERIA = ["magyar", "pontosság", "biztonság", "hasznosság", "utasításkövetés"]


def _average(scores: list[dict[str, Any]], criterion: str) -> str:
    if not scores:
        return "—"
    values = [sum(score[c] for c in CRITERIA) / len(CRITERIA) if criterion == "átlag" else score[criterion] for score in scores]
    return f"{sum(values) / len(values):.2f}"


def report(rows: list[dict[str, Any]], spent: float, setup: dict[str, Any]) -> str:
    judges = setup["judges"]
    lines = [f"# Asszisztens-modellteszt\n\nÖsszköltség: {spent:.2f} USD. Szintetikus demóadat, vak páros bírálat. Bíró(k): {', '.join(judges)}.\n"]
    for name, (entry_a, entry_b, _) in setup["comparisons"].items():
        model_a, model_b = contestant(entry_a)["label"], contestant(entry_b)["label"]
        group = [row for row in rows if row["comparison"] == name]
        if not group:
            continue
        models = [model_a, model_b]
        lines.append(f"\n## {name} ({len(group)} eset)\n")
        lines.append("| Bíró | Szempont | " + " | ".join(models) + " |\n|---|---|---|---|")
        for judge in judges:
            for criterion in CRITERIA + ["átlag"]:
                cells = [_average([row["verdicts"][judge]["scores"][model] for row in group if "scores" in row["verdicts"].get(judge, {})], criterion) for model in models]
                lines.append(f"| {judge} | {criterion} | " + " | ".join(cells) + " |")
        lines.append("\n**Melyik válasz volt jobb:**\n")
        for judge in judges:
            winners = [row["verdicts"][judge]["winner"] for row in group if "winner" in row["verdicts"].get(judge, {})]
            lines.append(f"- {judge}: {model_a} {winners.count(model_a)} · {model_b} {winners.count(model_b)} · döntetlen {winners.count('döntetlen')}")
        if len(judges) > 1:
            both = [row for row in group if all("winner" in row["verdicts"].get(judge, {}) for judge in judges)]
            same = sum(1 for row in both if len({row["verdicts"][judge]["winner"] for judge in judges}) == 1)
            lines.append(f"- A bírók egyetértése: {same}/{len(both)} esetben")
        lines.append("\n**Átlagpontszám kategóriánként:**\n\n| Kategória | " + " | ".join(models) + " |\n|---|---|---|")
        for category in sorted({row["case"]["category"] for row in group}):
            cells = [_average([row["verdicts"][judge]["scores"][model] for row in group if row["case"]["category"] == category
                               for judge in judges if "scores" in row["verdicts"].get(judge, {})], "átlag") for model in models]
            lines.append(f"| {category} | " + " | ".join(cells) + " |")
        lines.append("\n| Mérőszám | " + " | ".join(models) + " |\n|---|---|---|")
        for label, key, fmt in (("Átlagos költség / válasz (USD)", "cost", "{:.4f}"), ("Átlagos válaszidő (s)", "latency", "{:.1f}"),
                                ("Átlagos hossz (szó)", "words", "{:.0f}"), ("Kimeneti token / válasz", "output_tokens", "{:.0f}")):
            cells = []
            for model in models:
                values = [row["answers"][model][key] for row in group if key in row["answers"][model]]
                cells.append(fmt.format(sum(values) / len(values)) if values else "—")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        for label, test in (("Ellenőrizetlen számot tartalmazó válasz", lambda a: bool(a.get("unsupported_numbers"))),
                            ("Emojit tartalmazó válasz", lambda a: bool(a.get("emoji"))),
                            ("Hiba / elutasítás", lambda a: "error" in a or a.get("stop_reason") == "refusal"),
                            ("Tervjavaslatot tett", lambda a: bool(a.get("proposals"))),
                            ("Érvénytelen (elutasított) tervjavaslat", lambda a: bool(a.get("invalid_proposals")))):
            lines.append(f"| {label} | " + " | ".join(str(sum(1 for row in group if test(row["answers"][model]))) for model in models) + " |")
        checked = [row for row in group if row["answers"][models[0]].get("proposal_ok") is not None or row["answers"][models[1]].get("proposal_ok") is not None]
        if checked:
            cells = [f"{sum(1 for row in checked if row['answers'][model].get('proposal_ok'))}/{len(checked)}" for model in models]
            lines.append("| Tervjavaslat-elvárás teljesült | " + " | ".join(cells) + " |")
        lines.append("\n### Esetenként (bírói indoklással)\n")
        for row in group:
            for judge in judges:
                verdict = row["verdicts"].get(judge, {})
                lines.append(f"- **{row['case']['id']}** ({row['case']['category']}) – {judge}: {verdict.get('winner', '—')}. {verdict.get('reason', verdict.get('error', ''))}")
            for model in models:
                for item in row["answers"][model].get("proposals") or []:
                    lines.append(f"  - {model} javaslata: {item['summary']}" + ("" if row["answers"][model].get("proposal_ok") in (None, True) else " (**elvárással ellentétes**)"))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
