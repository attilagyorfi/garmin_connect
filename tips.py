"""Deterministic, explainable tips and a weekly digest from the athlete's own Garmin data.

Each rule looks at one signal (load ramp, HRV, resting pulse, sleep, intensity mix, consistency,
records, VO2max, strength frequency, steps) and, when it fires, says what happened, why the tip
appeared and what to do. No rule diagnoses anything; health-adjacent tips point to rest or a
professional rather than to a cause.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

MAX_TIPS = 6


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def _tip(key: str, tone: str, priority: int, title: str, message: str, why: str, action: str) -> dict[str, Any]:
    return {"key": key, "tone": tone, "priority": priority, "title": title, "message": message, "why": why, "action": action}


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce") if column in frame else pd.Series(dtype=float)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def load_ramp_tip(wellness: pd.DataFrame) -> dict[str, Any] | None:
    atl, ctl = _series(wellness, "hybrid_atl").iloc[-1:], _series(wellness, "hybrid_ctl").iloc[-1:]
    if atl.empty or ctl.empty or pd.isna(atl.iloc[0]) or pd.isna(ctl.iloc[0]) or ctl.iloc[0] < 5:
        return None
    ratio = float(atl.iloc[0] / ctl.iloc[0])
    why = f"A rövid távú (7 napos) terhelésed a hosszú távú (42 napos) szint {_fmt(ratio * 100, 0)}%-a."
    if ratio > 1.5:
        return _tip("load_ramp", "warn", 90, "Túl gyorsan nőtt a terhelésed",
                    "Az elmúlt napokban jóval többet edzettél, mint amihez a szervezeted hozzászokott.", why,
                    "Iktass be 1–2 könnyű vagy pihenőnapot, és a következő héten ne emeld tovább a volument.")
    if ratio > 1.3:
        return _tip("load_ramp", "warn", 70, "Emelkedik a terhelés",
                    "A terhelésed a szokásosnál gyorsabban nő; ez még kezelhető, de figyelni kell rá.", why,
                    "Tartsd a mostani szintet egy hétig, mielőtt tovább növelnéd.")
    if ratio < 0.75 and ctl.iloc[0] >= 10:
        return _tip("load_ramp", "nudge", 40, "Visszaesett az edzésmennyiség",
                    "Az utóbbi napokban kevesebbet edzettél a megszokottnál; ha nem tudatos pihenőhét, érdemes visszatérni a ritmushoz.", why,
                    "Tervezz be a következő 3 napra legalább két közepes edzést.")
    return None


def hrv_tip(wellness: pd.DataFrame) -> dict[str, Any] | None:
    hrv = _series(wellness, "hrv")
    recent, baseline = hrv.iloc[-7:].dropna(), hrv.iloc[-35:-7].dropna()
    if len(recent) < 4 or len(baseline) < 10:
        return None
    change = (recent.mean() / baseline.median() - 1) * 100
    why = f"Az elmúlt 7 nap átlagos HRV-je {_fmt(recent.mean(), 0)} ms, a megelőző 4 hét mediánja {_fmt(baseline.median(), 0)} ms ({'+' if change >= 0 else ''}{_fmt(change, 0)}%)."
    if change <= -10:
        return _tip("hrv", "warn", 80, "A HRV-d a szokásosnál alacsonyabb",
                    "A tartósan alacsonyabb HRV gyakran fáradtságot, stresszt vagy kevés alvást jelez.", why,
                    "A következő napokban válassz könnyebb edzést, és figyelj az alvásra; ha betegnek érzed magad, pihenj.")
    if change >= 5:
        return _tip("hrv", "celebrate", 50, "Jól regenerálódsz",
                    "A HRV-d a saját megszokott szinted fölött van, ami jó alkalmazkodásra utal.", why,
                    "Ha a többi jel is rendben van, ez jó időszak egy minőségi edzéshez.")
    return None


def resting_hr_tip(wellness: pd.DataFrame) -> dict[str, Any] | None:
    rhr = _series(wellness, "resting_hr")
    recent, baseline = rhr.iloc[-3:].dropna(), rhr.iloc[-31:-3].dropna()
    if len(recent) < 2 or len(baseline) < 10:
        return None
    difference = recent.mean() - baseline.median()
    if difference < 5:
        return None
    return _tip("resting_hr", "warn", 85, "Megemelkedett a nyugalmi pulzusod",
                f"Az utóbbi napokban kb. {_fmt(difference, 0)} ütés/perccel magasabb a szokásosnál.",
                f"Az elmúlt {len(recent)} nap átlaga {_fmt(recent.mean(), 0)} ütés/perc, a megelőző 4 hét mediánja {_fmt(baseline.median(), 0)} ütés/perc.",
                "Ez fáradtság, kevés alvás, stressz vagy kezdődő betegség jele is lehet: ma inkább könnyű mozgás vagy pihenő legyen. Ha tünetet is észlelsz, kérd szakember tanácsát.")


def sleep_tip(wellness: pd.DataFrame) -> dict[str, Any] | None:
    nights = _series(wellness, "sleep_hours").iloc[-7:].dropna()
    if len(nights) < 5:
        return None
    short = int((nights < 6).sum())
    why = f"Az elmúlt {len(nights)} éjszaka átlaga {_fmt(nights.mean())} óra; {short} éjszaka volt 6 óránál rövidebb."
    if nights.mean() < 6.5 or short >= 3:
        return _tip("sleep", "warn", 75, "Alváshiány gyűlik",
                    "Az elmúlt héten keveset aludtál; ez rontja a regenerációt és a teljesítményt.", why,
                    "Próbálj a következő napokban 30–60 perccel korábban lefeküdni, és a kemény edzést tedd egy kipihent nap utánra.")
    if (nights >= 7).all():
        return _tip("sleep", "celebrate", 30, "Minden éjjel kialudtad magad",
                    "Az elmúlt héten minden éjszaka legalább 7 órát aludtál.", why, "Tartsd ezt a ritmust – ez a fejlődés egyik alapja.")
    return None


def intensity_tip(activities: pd.DataFrame, today: date) -> dict[str, Any] | None:
    if activities.empty or "hr_zone_minutes" not in activities:
        return None
    recent = activities[(activities["date"].dt.date > today - timedelta(days=7)) & activities["hr_zone_minutes"].notna()]
    total = float(_series(recent, "duration_min").fillna(0).sum())
    zone2, high = float(_series(recent, "zone2_min").fillna(0).sum()), float(_series(recent, "high_intensity_min").fillna(0).sum())
    if total < 90 or zone2 + high <= 0:
        return None
    high_share, zone2_share = high / total, zone2 / total
    why = f"Az elmúlt 7 nap pulzuszónás edzésidejéből {_fmt(high_share * 100, 0)}% volt magas intenzitású, {_fmt(zone2_share * 100, 0)}% 2-es zónás."
    if high_share > 0.25:
        return _tip("intensity", "warn", 60, "Sok a magas intenzitás",
                    "Az állóképességi edzéseid nagy része kemény tartományban zajlott; ez hosszabb távon fárasztó.", why,
                    "Az edzésidő nagyjából 80%-a legyen könnyű (2-es zóna), és csak kb. 20% intenzív.")
    if zone2_share < 0.4:
        return _tip("intensity", "nudge", 35, "Kevés a könnyű alapozó munka",
                    "A 2-es zónás, beszélgetős tempójú edzés építi leghatékonyabban az aerob alapot.", why,
                    "A következő héten legyen legalább 2 hosszabb, könnyű tempójú edzésed.")
    return None


def inactivity_tip(activities: pd.DataFrame, today: date) -> dict[str, Any] | None:
    if activities.empty:
        return None
    days = (today - activities["date"].max().date()).days
    if days < 4:
        return None
    return _tip("inactivity", "nudge", 55, f"{days} napja nem edzettél",
                "Egy rövid, könnyű edzés is segít megtartani a ritmust és a motivációt.",
                f"Az utolsó rögzített edzésed {days} napja volt.", "Ma egy 20–30 perces könnyű mozgás is elég a visszatéréshez.")


def _weekly_sessions(activities: pd.DataFrame) -> dict[date, dict[str, float]]:
    weeks: dict[date, dict[str, float]] = {}
    for _, row in activities.iterrows():
        week = _week_start(row["date"].date())
        item = weeks.setdefault(week, {"sessions": 0, "minutes": 0.0, "load": 0.0})
        item["sessions"] += 1
        item["minutes"] += float(row.get("duration_min") or 0)
        item["load"] += float(row.get("session_load") or 0) if pd.notna(row.get("session_load")) else 0.0
    return weeks


def streak_tip(activities: pd.DataFrame, today: date) -> dict[str, Any] | None:
    if activities.empty:
        return None
    weeks = _weekly_sessions(activities)
    cursor, streak = _week_start(today) - timedelta(days=7), 0
    while weeks.get(cursor, {}).get("sessions", 0) >= 3:
        streak += 1
        cursor -= timedelta(days=7)
    if streak < 3:
        return None
    return _tip("streak", "celebrate", 45 + min(20, streak), f"{streak} hete tartod a ritmust",
                f"Egymás után {streak} héten át legalább 3 edzést teljesítettél.", "A következetesség a fejlődés legerősebb mozgatója.",
                "Csak így tovább – a következő héten is tervezz be legalább 3 edzést.")


def volume_change_tip(activities: pd.DataFrame, today: date) -> dict[str, Any] | None:
    if activities.empty:
        return None
    weeks = _weekly_sessions(activities)
    last_week = _week_start(today) - timedelta(days=7)
    current, previous = weeks.get(last_week, {}).get("minutes", 0), weeks.get(last_week - timedelta(days=7), {}).get("minutes", 0)
    if previous < 60:
        return None
    change = round((current / previous - 1) * 100)  # same rounding as the weekly digest shows
    why = f"A múlt héten {_fmt(current, 0)} percet edzettél, az azelőttin {_fmt(previous, 0)} percet ({'+' if change >= 0 else ''}{_fmt(change, 0)}%)."
    if change >= 30:
        return _tip("volume", "warn", 65, "Nagyot ugrott a heti edzésidő",
                    "A heti edzésidő hirtelen, 30%-nál nagyobb növelése emeli a túlterhelés kockázatát.", why,
                    "A következő héten tartsd vagy kicsit csökkentsd ezt a mennyiséget.")
    if change <= -40:
        return _tip("volume", "info", 30, "Könnyebb hét volt",
                    "A múlt héten jóval kevesebbet edzettél; ha tudatos pihenőhét volt, ez jó a regenerációnak.", why,
                    "Ha nem volt tervezett, a következő héten fokozatosan térj vissza a szokásos mennyiséghez.")
    return None


RECORD_IS_DISTANCE = {7}


def _format_record(record: dict[str, Any]) -> str:
    value = float(record["value"])
    if record.get("type_id") in RECORD_IS_DISTANCE:
        return f"{_fmt(value / 1000)} km"
    hours, rest = divmod(int(round(value)), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def record_tip(athlete: dict[str, Any] | None, today: date) -> dict[str, Any] | None:
    recent = [item for item in (athlete or {}).get("personal_records") or []
              if item.get("label") and item.get("date") and date.fromisoformat(item["date"]) >= today - timedelta(days=21)]
    if not recent:
        return None
    record = max(recent, key=lambda item: item["date"])
    return _tip("record", "celebrate", 75, f"Új egyéni csúcs: {record['label']}",
                f"{date.fromisoformat(record['date']).strftime('%m. %d.')}-én {_format_record(record)} lett az új legjobb eredményed.",
                "A Garmin az elmúlt 3 hétben új személyes rekordot rögzített.", "Ünnepeld meg – és a következő napokban hagyj időt a regenerációra.")


def vo2max_tip(athlete: dict[str, Any] | None, today: date) -> dict[str, Any] | None:
    history = [item for item in (athlete or {}).get("vo2max_history") or [] if item.get("running")]
    if len(history) < 2:
        return None
    latest = history[-1]
    earlier = [item for item in history if date.fromisoformat(item["date"]) <= date.fromisoformat(latest["date"]) - timedelta(days=28)]
    if not earlier:
        return None
    previous = earlier[-1]
    change = latest["running"] - previous["running"]
    why = f"{previous['date']}: {_fmt(previous['running'])} → {latest['date']}: {_fmt(latest['running'])} ml/kg/perc."
    if change >= 1:
        return _tip("vo2max", "celebrate", 60, f"Nőtt a VO2max-od (+{_fmt(change)})",
                    "Az aerob kapacitásod javult – az állóképességi munka meghozta az eredményét.", why,
                    "Nézd meg a „Hol tartasz?” oldalon, hol állsz most a korosztályodban.")
    if change <= -1.5:
        return _tip("vo2max", "info", 50, "Csökkent a becsült VO2max-od",
                    "A becslést a kevesebb vagy könnyebb futás, a hőség és a fáradtság is lefelé húzhatja.", why,
                    "Ha ez tartós, építs be heti egy intervallumos és egy hosszabb, könnyű futást.")
    return None


def benchmark_tips(benchmarks: dict[str, Any] | None) -> list[dict[str, Any]]:
    cards = {card["key"]: card for card in (benchmarks or {}).get("cards", []) if card.get("status") == "ok"}
    tips = []
    strength = cards.get("strength")
    if strength and strength.get("value") is not None and strength["value"] < 2:
        tips.append(_tip("strength", "nudge", 40, "Kevés az erősítés",
                         f"Az elmúlt 4 hétben átlagosan heti {_fmt(strength['value'])} erőedzésed volt.",
                         "A WHO hetente legalább 2 nap izomerősítő mozgást ajánl; ez az állóképességi sportolóknak is segít a sérülésmegelőzésben.",
                         strength.get("nextGoal") or "Tervezz be heti 2 rövid, teljes testes erősítő edzést."))
    steps = cards.get("steps")
    if steps and (steps.get("level") or 0) <= 1:
        tips.append(_tip("steps", "nudge", 25, "Mozogj többet a hétköznapokban",
                         f"Átlagosan {steps['valueText']} – ez a korodnak megfelelő sáv alatt van.", steps.get("headline") or "",
                         steps.get("nextGoal") or "Iktass be napi egy 15–20 perces sétát."))
    return tips


def generate_tips(wellness: pd.DataFrame, activities: pd.DataFrame, athlete: dict[str, Any] | None,
                  benchmarks: dict[str, Any] | None, today: date) -> list[dict[str, Any]]:
    candidates = [
        load_ramp_tip(wellness), hrv_tip(wellness), resting_hr_tip(wellness), sleep_tip(wellness),
        intensity_tip(activities, today), inactivity_tip(activities, today), streak_tip(activities, today),
        volume_change_tip(activities, today), record_tip(athlete, today), vo2max_tip(athlete, today),
        *benchmark_tips(benchmarks),
    ]
    tips = sorted((tip for tip in candidates if tip), key=lambda tip: -tip["priority"])
    selected = tips[:MAX_TIPS]
    # Keep the list motivating: when only warnings made the cut, swap in the best positive signal.
    if not any(tip["tone"] == "celebrate" for tip in selected):
        positive = next((tip for tip in tips[MAX_TIPS:] if tip["tone"] == "celebrate"), None)
        if positive and len(selected) == MAX_TIPS:
            selected[-1] = positive
    return selected


def weekly_digest(wellness: pd.DataFrame, activities: pd.DataFrame, tips: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    week_start = _week_start(today) - timedelta(days=7)
    week_end = week_start + timedelta(days=6)
    if activities.empty:
        return None
    dates = activities["date"].dt.date
    week = activities[(dates >= week_start) & (dates <= week_end)]
    previous = activities[(dates >= week_start - timedelta(days=7)) & (dates < week_start)]
    minutes, previous_minutes = float(week["duration_min"].fillna(0).sum()), float(previous["duration_min"].fillna(0).sum())
    load = float(_series(week, "session_load").fillna(0).sum())
    strength_minutes = float(week[week["modality"].astype(str).str.contains("Strength", case=False)]["duration_min"].fillna(0).sum()) if "modality" in week else 0.0
    days = wellness[(wellness.index.date >= week_start) & (wellness.index.date <= week_end)]
    sleep = _series(days, "sleep_hours").dropna()
    hrv, baseline = _series(days, "hrv").dropna(), _series(wellness[wellness.index.date < week_start], "hrv").dropna().tail(28)
    longest = week.sort_values("duration_min", ascending=False).head(1)
    change = (minutes / previous_minutes - 1) * 100 if previous_minutes >= 30 else None
    parts = [f"{len(week)} edzés, {_fmt(minutes / 60)} óra edzésidő"]
    if change is not None:
        parts.append(f"{'+' if change >= 0 else ''}{_fmt(change, 0)}% az előző héthez képest")
    summary = "A múlt héten " + ", ".join(parts) + "."
    if not longest.empty:
        row = longest.iloc[0]
        summary += f" A leghosszabb edzésed: {row['name']} ({_fmt(float(row['duration_min']), 0)} perc)."
    if len(sleep):
        summary += f" Átlagosan {_fmt(sleep.mean())} órát aludtál."
    hrv_change = (hrv.mean() / baseline.median() - 1) * 100 if len(hrv) >= 3 and len(baseline) >= 10 else None
    if hrv_change is not None:
        summary += f" A HRV-d {_fmt(abs(hrv_change), 0)}%-kal {'magasabb' if hrv_change >= 0 else 'alacsonyabb'} volt a megszokottnál."
    highlights = [tip["title"] for tip in tips if tip["tone"] == "celebrate"][:3]
    focus = next((tip["action"] for tip in tips if tip["tone"] in ("warn", "nudge")), "Tartsd a mostani, kiegyensúlyozott ritmust.")
    return {
        "weekStart": week_start.isoformat(), "weekEnd": week_end.isoformat(),
        "sessions": len(week), "minutes": round(minutes), "load": round(load), "strengthMinutes": round(strength_minutes),
        "changePct": round(change) if change is not None else None,
        "sleepHours": round(float(sleep.mean()), 1) if len(sleep) else None,
        "hrvChangePct": round(hrv_change) if hrv_change is not None else None,
        "summary": summary, "highlights": highlights, "focus": focus,
    }


def coaching_payload(wellness: pd.DataFrame, activities: pd.DataFrame, athlete: dict[str, Any] | None,
                     benchmarks: dict[str, Any] | None, today: date) -> dict[str, Any]:
    tips = generate_tips(wellness, activities, athlete, benchmarks, today)
    return {"tips": tips, "weekly": weekly_digest(wellness, activities, tips, today)}
