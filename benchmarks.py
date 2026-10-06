""""Hol tartasz?" – the athlete's metrics compared with sourced, age- and sex-specific references.

Every number below comes from a cited, openly licensed or public-domain source (see SOURCES).
Comparisons are motivational context, not a medical assessment: each card carries its own
confidence and caveat, and nothing is shown when sex, age or the metric itself is missing.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import erf, sqrt
from statistics import median
from typing import Any

SOURCES = {
    "hunt2013": {
        "label": "HUNT 3 Fitness Study (Norvégia, közvetlenül mért VO2max)",
        "citation": "Loe H, Rognmo Ø, Saltin B, Wisløff U. Aerobic Capacity Reference Data in 3816 Healthy Men and Women 20–90 Years. PLoS ONE 2013;8(5):e64319 (helyesbítéssel).",
        "url": "https://doi.org/10.1371/journal.pone.0064319", "license": "CC BY 4.0",
    },
    "ehis2019": {
        "label": "Eurostat – Európai lakossági egészségfelmérés (EHIS), Magyarország, 2019",
        "citation": "Eurostat: hlth_ehis_pe2e (aerob mozgással töltött heti idő) és hlth_ehis_pe9e (egészségjavító mozgás), 2019.",
        "url": "https://doi.org/10.2908/HLTH_EHIS_PE2E", "license": "CC BY 4.0",
    },
    "nhanes2011": {
        "label": "CDC/NCHS – nyugalmi pulzus referenciaadatok (NHANES 1999–2008)",
        "citation": "Ostchega Y, Porter KS, Hughes J, Dillon CF, Nwankwo T. Resting pulse rate reference data for children, adolescents, and adults: United States, 1999–2008. National Health Statistics Reports No. 41, 2011.",
        "url": "https://www.cdc.gov/nchs/data/nhsr/nhsr041.pdf", "license": "Közkincs (U.S. Government)",
    },
    "paluch2022": {
        "label": "Napi lépésszám és halálozás – 15 kohorsz metaanalízise",
        "citation": "Paluch AE, Bajpai S, Bassett DR, et al. Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts. Lancet Public Health 2022;7(3):e219–e228.",
        "url": "https://doi.org/10.1016/S2468-2667(21)00302-9", "license": "CC BY 4.0",
    },
    "aasm2015": {
        "label": "AASM/SRS konszenzus az ajánlott alvásmennyiségről",
        "citation": "Watson NF, Badr MS, Belenky G, et al. Recommended Amount of Sleep for a Healthy Adult. Sleep 2015;38(6):843–844.",
        "url": "https://doi.org/10.5665/sleep.4716", "license": "Hivatkozás (ajánlás)",
    },
    "who2020": {
        "label": "WHO-irányelv a fizikai aktivitásról (2020)",
        "citation": "World Health Organization. WHO guidelines on physical activity and sedentary behaviour. Genf, 2020.",
        "url": "https://www.who.int/publications/i/item/9789240015128", "license": "Hivatkozás (ajánlás)",
    },
    "garmin": {
        "label": "Garmin Connect fittségi kor",
        "citation": "A Garmin saját fittségikor-számítása (VO2max, nyugalmi pulzus, intenzív percek és BMI alapján).",
        "url": "https://www.garmin.com", "license": "A felhasználó saját Garmin-adata",
    },
}

# HUNT 3 Fitness, Table 2: VO2max (mL·kg⁻¹·min⁻¹) mean and SD per sex and age decade (corrected table).
VO2MAX_HUNT = {
    "male": [(20, 29, 54.4, 8.4), (30, 39, 49.1, 7.5), (40, 49, 47.2, 7.7), (50, 59, 42.6, 7.4), (60, 69, 39.2, 6.7), (70, 120, 35.3, 6.5)],
    "female": [(20, 29, 43.0, 7.7), (30, 39, 40.0, 6.8), (40, 49, 38.4, 6.9), (50, 59, 34.4, 5.7), (60, 69, 31.1, 5.1), (70, 120, 28.3, 5.2)],
}

# NHANES 1999–2008 resting pulse (beats/min), Tables 2–3: percentiles 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99.
RHR_PERCENTILES = (1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99)
RHR_NHANES = {
    "male": [(20, 39, (47, 50, 52, 55, 61, 69, 76, 84, 89, 95, 101)), (40, 59, (46, 49, 52, 55, 61, 68, 77, 85, 90, 95, 104)),
             (60, 79, (45, 48, 50, 54, 60, 67, 75, 84, 91, 98, 102)), (80, 120, (None, 48, 51, 54, 61, 68, 78, 86, 94, 97, None))],
    "female": [(20, 39, (52, 55, 57, 60, 66, 74, 82, 89, 95, 99, 104)), (40, 59, (51, 53, 56, 59, 64, 71, 79, 86, 92, 97, 101)),
               (60, 79, (52, 54, 56, 59, 64, 70, 78, 86, 92, 96, 102)), (80, 120, (None, 53, 56, 59, 64, 71, 77, 85, 93, 98, 100))],
}

# Eurostat EHIS 2019, Hungary: share (%) of each age group by weekly non-work aerobic activity time:
# 0 min, 1–149 min, 150–299 min, ≥300 min (hlth_ehis_pe2e).
EHIS_AGE_GROUPS = [(18, 24, "Y18-24"), (25, 34, "Y25-34"), (35, 44, "Y35-44"), (45, 54, "Y45-54"), (55, 64, "Y55-64"), (65, 74, "Y65-74"), (75, 120, "Y_GE75")]
AEROBIC_HU_2019 = {
    "male": {"Y18-24": (23.9, 23.2, 19.8, 33.1), "Y25-34": (29.8, 28.9, 17.4, 23.8), "Y35-44": (33.9, 26.9, 20.3, 19.0), "Y45-54": (38.7, 29.7, 18.7, 12.9),
             "Y55-64": (50.6, 26.0, 8.3, 15.1), "Y65-74": (44.6, 28.1, 8.6, 18.7), "Y_GE75": (65.3, 14.0, 8.0, 12.8)},
    "female": {"Y18-24": (31.0, 34.5, 19.5, 15.0), "Y25-34": (34.5, 31.9, 17.5, 16.1), "Y35-44": (31.7, 32.5, 19.0, 16.8), "Y45-54": (35.7, 31.1, 14.5, 18.6),
               "Y55-64": (42.1, 30.3, 11.7, 15.9), "Y65-74": (56.5, 20.4, 8.5, 14.7), "Y_GE75": (75.8, 15.1, 3.5, 5.6)},
}
# Eurostat EHIS 2019, Hungary: share (%) doing muscle-strengthening activity (hlth_ehis_pe9e, MV_MSC).
MUSCLE_HU_2019 = {
    "male": {"Y18-24": 47.8, "Y25-34": 33.7, "Y35-44": 29.4, "Y45-54": 22.9, "Y55-64": 13.4, "Y65-74": 20.1, "Y_GE75": 11.3},
    "female": {"Y18-24": 31.1, "Y25-34": 29.8, "Y35-44": 28.2, "Y45-54": 19.3, "Y55-64": 16.4, "Y65-74": 18.4, "Y_GE75": 8.0},
}

LEVELS = [(95, "elit"), (80, "kiváló"), (60, "jó"), (25, "átlagos"), (0, "építkező")]
SEX_LABEL = {"male": "férfiak", "female": "nők"}


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def _normal_ppf(p: float) -> float:
    low, high = -8.0, 8.0
    for _ in range(80):
        mid = (low + high) / 2
        low, high = (mid, high) if _normal_cdf(mid) < p else (low, mid)
    return (low + high) / 2


def _article(word: str) -> str:
    return "az" if word[:1].lower() in "aáeéiíoóöőuúüű" else "a"


def level_for(percentile: float) -> tuple[int, str]:
    percentile = round(percentile)
    for index, (threshold, name) in enumerate(LEVELS):
        if percentile >= threshold:
            return len(LEVELS) - 1 - index, name
    return 0, LEVELS[-1][1]


def _next_threshold(percentile: float) -> tuple[int, str] | None:
    percentile = round(percentile)
    for threshold, name in reversed(LEVELS[:-1]):
        if percentile < threshold:
            return threshold, name
    return None


def _group(table: list[tuple], age: int) -> tuple | None:
    return next((row for row in table if row[0] <= age <= row[1]), None)


def _cohort(row: tuple, sex: str, hungarian: bool = False) -> str:
    low, high = row[0], row[1]
    ages = f"{low}+ éves" if high >= 120 else f"{low}–{high} éves"
    return f"{ages} {'magyar ' if hungarian else ''}{SEX_LABEL[sex]}"


def _card(key: str, title: str, **fields: Any) -> dict[str, Any]:
    return {"key": key, "title": title, "status": "ok", "percentile": None, "atLeast": False, "level": None, "category": None,
            "trend": None, "nextGoal": None, "caveat": None, "confidence": "közepes", **fields}


def _missing(key: str, title: str, reason: str, sources: list[str]) -> dict[str, Any]:
    return _card(key, title, status="missing", headline=reason, sources=sources, valueText="—", confidence=None)


def vo2max_percentile(value: float, sex: str, age: int) -> tuple[float, tuple] | None:
    row = _group(VO2MAX_HUNT[sex], age)
    if not row:
        return None
    return 100 * _normal_cdf((value - row[2]) / row[3]), row


def vo2max_card(athlete: dict[str, Any], today: date) -> dict[str, Any]:
    title, sources = "VO2max – aerob kapacitás", ["hunt2013"]
    sex, age, value = athlete.get("sex"), athlete.get("age"), athlete.get("vo2max_running")
    if not value:
        return _missing("vo2max", title, "Nincs futásból becsült VO2max-érték; egy pulzusmérős, szabadtéri futás után a Garmin kiszámolja.", sources)
    if sex not in VO2MAX_HUNT or not age or age < 20:
        return _missing("vo2max", title, "Az összevetéshez add meg a nemed és a születési dátumod a Garminban.", sources)
    percentile, row = vo2max_percentile(value, sex, age)
    level, category = level_for(percentile)
    target = _next_threshold(percentile)
    next_goal = None
    if target:
        needed = row[2] + row[3] * _normal_ppf(target[0] / 100)
        next_goal = f"+{_fmt(max(0.1, needed - value))} ml/kg/perc kell {_article(target[1])} „{target[1]}” szinthez ({target[0]}. percentilis)."
    trend = None
    history = [item for item in athlete.get("vo2max_history") or [] if item.get("running")]
    past = [item for item in history if date.fromisoformat(item["date"]) <= today - timedelta(days=80)]
    if past:
        previous = past[-1]
        past_percentile = vo2max_percentile(previous["running"], sex, age)[0]
        change = percentile - past_percentile
        trend = f"{date.fromisoformat(previous['date']).strftime('%Y. %m. %d.')}: {_fmt(previous['running'])} ml/kg/perc ({round(past_percentile)}. percentilis) → most {round(percentile)}. ({'+' if change >= 0 else ''}{round(change)} pont)."
    return _card(
        "vo2max", title, value=value, valueText=f"{_fmt(value)} ml/kg/perc", percentile=round(percentile), level=level, category=category,
        cohort=_cohort(row, sex), headline=f"Jobb, mint a veled egykorú {SEX_LABEL[sex]} kb. {round(percentile)}%-áé.",
        detail=f"Referencia: {_cohort(row, sex)} átlaga {_fmt(row[2])} ml/kg/perc (szórás {_fmt(row[3])}).",
        trend=trend, nextGoal=next_goal, sources=sources,
        caveat="A Garmin a VO2max-ot pulzusból és tempóból becsüli, a referencia laborban mért érték egészséges norvég felnőttektől, akik az átlagnál edzettebbek lehetnek.",
    )


def _ehis_group(age: int) -> tuple | None:
    return next((row for row in EHIS_AGE_GROUPS if row[0] <= age <= row[1]), None)


def aerobic_percentile(minutes: float, shares: tuple[float, float, float, float]) -> tuple[float, bool]:
    zero, low, mid, high = shares
    if minutes <= 0:
        return 0.0, False
    if minutes < 150:
        return zero + low * (minutes - 1) / 149, False
    if minutes < 300:
        return zero + low + mid * (minutes - 150) / 150, False
    return zero + low + mid, True


def aerobic_card(athlete: dict[str, Any], today: date) -> dict[str, Any]:
    title, sources = "Heti aerob mozgás", ["ehis2019", "who2020"]
    sex, age = athlete.get("sex"), athlete.get("age")
    current_monday = today - timedelta(days=today.weekday())
    weeks = [item for item in athlete.get("intensity_weeks") or [] if date.fromisoformat(item["week_start"]) < current_monday][-4:]
    if not weeks:
        return _missing("aerobic", title, "Még nincs elég heti intenzív perc adat (a Garmin a mérsékelt és intenzív perceket számolja).", sources)
    minutes = sum(item["moderate"] + item["vigorous"] for item in weeks) / len(weeks)
    equivalent = sum(item["equivalent"] for item in weeks) / len(weeks)
    who = "teljesíted a WHO bővített ajánlását (300+ perc)" if equivalent >= 300 else "teljesíted a WHO-ajánlást (150+ perc)" if equivalent >= 150 else f"a WHO-ajánláshoz még {round(150 - equivalent)} perc hiányzik hetente"
    group = _ehis_group(age) if age else None
    if sex not in AEROBIC_HU_2019 or not group:
        return _card("aerobic", title, value=round(minutes), valueText=f"{round(minutes)} perc/hét", headline=f"Az elmúlt {len(weeks)} hét átlagában {who}.",
                     sources=sources, confidence="magas")
    shares = AEROBIC_HU_2019[sex][group[2]]
    percentile, at_least = aerobic_percentile(minutes, shares)
    level, category = level_for(percentile)
    cohort = _cohort(group, sex, hungarian=True)
    headline = (f"A {cohort} felső {_fmt(shares[3])}%-ába tartozol: ők mozognak heti 300 percnél többet." if at_least
                else f"Többet mozogsz, mint a {cohort} kb. {round(percentile)}%-a.")
    return _card(
        "aerobic", title, value=round(minutes), valueText=f"{round(minutes)} perc/hét", percentile=round(percentile), atLeast=at_least,
        level=level, category=category, cohort=cohort, headline=headline,
        detail=f"Az elmúlt {len(weeks)} lezárt hét átlaga. A {cohort} {_fmt(shares[0])}%-a egyáltalán nem végez szabadidős aerob mozgást. Intenzitással súlyozva (1 intenzív perc = 2 mérsékelt) {who}.",
        nextGoal=None if equivalent >= 300 else f"Heti {round(300 - equivalent)} további súlyozott perccel elérnéd a 300 perces bővített ajánlást.",
        sources=sources, confidence="közepes",
        caveat="A referencia kérdőíves, saját bevalláson alapuló adat a munkán kívüli aerob sportról; a Garmin minden mérsékelt és intenzív percet számol.",
    )


def strength_card(athlete: dict[str, Any], activities: list[dict[str, Any]], today: date, is_strength) -> dict[str, Any]:
    title, sources = "Rendszeres erősítés", ["ehis2019", "who2020"]
    cutoff = today - timedelta(days=28)
    sessions = 0
    for activity in activities:
        raw = str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or "")[:10]
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            continue
        if cutoff < day <= today and is_strength(activity):
            sessions += 1
    per_week = sessions / 4
    sex, age = athlete.get("sex"), athlete.get("age")
    group = _ehis_group(age) if age else None
    meets = per_week >= 2
    base = dict(value=round(per_week, 1), valueText=f"{_fmt(per_week)} edzés/hét", sources=sources, confidence="közepes",
                detail=f"Az elmúlt 4 hétben {sessions} erőedzést rögzítettél. A WHO legalább heti 2 nap izomerősítést ajánl.",
                caveat="A referencia kérdőíves adat az izomerősítő mozgás gyakoriságáról.")
    if sex not in MUSCLE_HU_2019 or not group:
        return _card("strength", title, headline="Teljesíted a heti 2 erősítő edzés ajánlást." if meets else "A WHO heti legalább 2 erősítő edzést ajánl.", **base)
    share = MUSCLE_HU_2019[sex][group[2]]
    cohort = _cohort(group, sex, hungarian=True)
    if meets:
        percentile = 100 - share
        level, category = level_for(percentile)
        return _card("strength", title, percentile=round(percentile), atLeast=True, level=level, category=category, cohort=cohort,
                     headline=f"A {cohort} csak {_fmt(share)}%-a erősít ilyen rendszeresen – te köztük vagy.", **base)
    return _card("strength", title, level=0, category="építkező", cohort=cohort,
                 headline=f"A {cohort} {_fmt(share)}%-a végez rendszeres izomerősítést.",
                 nextGoal=f"Heti {_fmt(2 - per_week)} további erőedzéssel teljesítenéd a heti 2 alkalmas ajánlást.", **base)


def rhr_percentile(value: float, points: tuple) -> float:
    pairs = [(p, v) for p, v in zip(RHR_PERCENTILES, points) if v is not None]
    if value <= pairs[0][1]:
        return pairs[0][0]
    if value >= pairs[-1][1]:
        return pairs[-1][0]
    for (p1, v1), (p2, v2) in zip(pairs, pairs[1:]):
        if v1 <= value <= v2:
            return p1 if v2 == v1 else p1 + (p2 - p1) * (value - v1) / (v2 - v1)
    return 50.0


def rhr_card(athlete: dict[str, Any], resting_hr: list[float]) -> dict[str, Any]:
    title, sources = "Nyugalmi pulzus", ["nhanes2011"]
    values = [value for value in resting_hr if value]
    sex, age = athlete.get("sex"), athlete.get("age")
    if len(values) < 3:
        return _missing("rhr", title, "Az elmúlt hétről nincs elég nyugalmi pulzus adat.", sources)
    value = median(values)
    if sex not in RHR_NHANES or not age or age < 20:
        return _missing("rhr", title, "Az összevetéshez add meg a nemed és a születési dátumod a Garminban.", sources)
    row = _group(RHR_NHANES[sex], age)
    lower_than = 100 - rhr_percentile(value, row[2])
    level, category = level_for(lower_than)
    return _card(
        "rhr", title, value=round(value), valueText=f"{round(value)} ütés/perc", percentile=round(lower_than), level=level, category=category,
        cohort=_cohort(row, sex), headline=f"Alacsonyabb, mint a veled egykorú {SEX_LABEL[sex]} kb. {round(lower_than)}%-áé.",
        detail=f"Az elmúlt {len(values)} nap mediánja. Referencia-medián: {row[2][5]} ütés/perc.", sources=sources, confidence="tájékoztató",
        caveat="A referenciát rendelőben, ülve mérték; a Garmin a nap legalacsonyabb nyugalmi értékét adja, ami jellemzően alacsonyabb, ezért az összevetés kedvezőbb képet mutathat.",
    )


def sleep_card(sleep_hours: list[float]) -> dict[str, Any]:
    title, sources = "Alvásmennyiség", ["aasm2015"]
    nights = [value for value in sleep_hours if value]
    if len(nights) < 5:
        return _missing("sleep", title, "Az elmúlt két hétről nincs elég alvásadat.", sources)
    average, enough = sum(nights) / len(nights), sum(1 for value in nights if value >= 7)
    ratio = enough / len(nights)
    level, category = (3, "kiváló") if ratio >= 0.85 else (2, "jó") if ratio >= 0.6 else (1, "átlagos") if ratio >= 0.35 else (0, "építkező")
    return _card(
        "sleep", title, value=round(average, 1), valueText=f"{_fmt(average)} óra/éj", level=level, category=category,
        headline=f"Az elmúlt {len(nights)} éjszakából {enough} volt legalább 7 órás.",
        detail="Felnőtteknek rendszeresen legalább 7 óra alvás ajánlott; ez a regeneráció és a teljesítmény egyik alapja.",
        nextGoal=None if ratio >= 0.85 else "Cél: a hét legalább 6 éjszakáján 7+ óra alvás.", sources=sources, confidence="magas",
    )


def steps_card(athlete: dict[str, Any]) -> dict[str, Any]:
    title, sources = "Napi lépésszám", ["paluch2022"]
    value, age = athlete.get("avg_daily_steps"), athlete.get("age")
    if not value:
        return _missing("steps", title, "Nincs napi lépésszám adat.", sources)
    low, high = (6000, 8000) if age and age >= 60 else (8000, 10000)
    level, category = (3, "kiváló") if value >= high else (2, "jó") if value >= low else (1, "átlagos") if value >= low * 0.7 else (0, "építkező")
    band = f"{_fmt(low, 0)}–{_fmt(high, 0)}"
    return _card(
        "steps", title, value=value, valueText=f"{_fmt(value, 0)} lépés/nap", level=level, category=category,
        headline=f"{'Eléred' if value >= high else 'Megközelíted' if value >= low else 'Még nem éred el'} a korodnak megfelelő {band} lépéses sávot.",
        detail=f"Egy 15 kohorszos metaanalízisben a halálozási kockázat {'60 év felett' if age and age >= 60 else '60 év alatt'} nagyjából {band} napi lépésig csökkent tovább.",
        nextGoal=None if value >= high else f"Napi kb. {_fmt(high - value, 0)} további lépés a sáv felső határáig.", sources=sources, confidence="magas",
    )


def fitness_age_card(athlete: dict[str, Any]) -> dict[str, Any]:
    title, sources = "Fittségi kor", ["garmin"]
    fitness, age = athlete.get("fitness_age"), athlete.get("age") or athlete.get("chronological_age")
    if not fitness or not age:
        return _missing("fitness_age", title, "A Garmin még nem számolt fittségi kort.", sources)
    difference = age - fitness
    level, category = (4, "elit") if difference >= 10 else (3, "kiváló") if difference >= 5 else (2, "jó") if difference >= 1 else (1, "átlagos") if difference > -3 else (0, "építkező")
    achievable = athlete.get("achievable_fitness_age")
    return _card(
        "fitness_age", title, value=round(fitness, 1), valueText=f"{_fmt(fitness)} év", level=level, category=category,
        headline=(f"{_fmt(difference)} évvel fiatalabb a naptári korodnál." if difference >= 0.5 else f"{_fmt(-difference)} évvel idősebb a naptári korodnál." if difference <= -0.5 else "Megegyezik a naptári koroddal."),
        detail="A Garmin a VO2max, a nyugalmi pulzus, a heti intenzív percek és a BMI alapján számolja.",
        nextGoal=f"A Garmin szerint elérhető fittségi kor: {_fmt(achievable)} év." if achievable and achievable < fitness - 0.4 else None,
        sources=sources, confidence="magas",
    )


def athlete_benchmarks(athlete: dict[str, Any] | None, activities: list[dict[str, Any]], resting_hr: list[float],
                       sleep_hours: list[float], today: date, is_strength) -> dict[str, Any] | None:
    if not athlete:
        return None
    cards = [
        vo2max_card(athlete, today), aerobic_card(athlete, today), strength_card(athlete, activities, today, is_strength),
        rhr_card(athlete, resting_hr), sleep_card(sleep_hours), steps_card(athlete), fitness_age_card(athlete),
    ]
    used = sorted({key for card in cards for key in card["sources"]}, key=list(SOURCES).index)
    return {"cards": cards, "sources": [{"key": key, **SOURCES[key]} for key in used], "demo": bool(athlete.get("demo")),
            "profile": {"sex": athlete.get("sex"), "age": athlete.get("age")}}
