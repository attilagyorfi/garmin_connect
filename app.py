"""Streamlit operator UI for explainable hybrid training decisions."""

from __future__ import annotations

import os
import calendar
import html
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    build_daily_frames, data_quality, explainable_readiness, personal_baseline,
    deload_taper_recommendation, evaluate_training_plans, event_preparation_analysis,
    mountain_readiness, mountain_weekly_trends, multiday_readiness, pattern_uncertainty, personal_patterns, plan_adjustment_message, red_flags, training_decision, tsb_zone,
    weekly_plan_template, weekly_summary,
)
from garmin_sync import GarminSync, GarminSyncError, demo_data
from storage import Database


st.set_page_config(page_title="Hibrid edzésdöntés", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1450px; padding-top: 1.4rem}
[data-testid="stMetric"] {background:#151b25; border:1px solid #2c3748; border-radius:12px; padding:14px}
.decision {padding:1.2rem 1.4rem;border-radius:14px;background:linear-gradient(135deg,#14263a,#18201f);border:1px solid #36556f}
.muted {color:#aeb9c8;font-size:.92rem}
.calendar-grid {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.45rem}
.calendar-head {text-align:center;color:#aeb9c8;font-size:.8rem;font-weight:700;padding:.35rem}
.calendar-day {min-height:112px;padding:.55rem;border-radius:10px;background:#151b25;border:1px solid #2c3748}
.calendar-day.today {border-color:#63b3ff;box-shadow:0 0 0 1px #63b3ff inset}
.calendar-day.empty {background:transparent;border-color:transparent}
.calendar-number {font-weight:800;margin-bottom:.35rem}.calendar-meta {font-size:.74rem;line-height:1.35;color:#c8d2df}
@media(max-width:700px){.block-container{padding:0.8rem}.decision{padding:1rem}}
@media(max-width:700px){.calendar-grid{grid-template-columns:repeat(7,minmax(70px,1fr));overflow-x:auto}.calendar-day{min-height:98px}}
</style>
""", unsafe_allow_html=True)

CACHE_DIR = Path(os.getenv("CACHE_DIR", "data"))
BASELINE_DAYS = int(os.getenv("BASELINE_DAYS", "28"))
db = Database(CACHE_DIR / "training.sqlite3")
sync = GarminSync(CACHE_DIR)

with st.sidebar:
    st.title("HIBRID // EDZŐ")
    page = st.radio("Navigáció", ["Ma", "Terhelés és trendek", "Naptár", "Egyensúly", "Hegyi felkészültség", "Mi működik nálam?", "Célok és tervek", "Heti jelentés", "Beállítások és módszertan"])
    st.divider()
    demo = st.toggle("Bemutató mód", value=not bool(os.getenv("GARMIN_EMAIL")), help="Legalább 90 nap determinisztikus mintaadat.")
    history_choice = st.selectbox("Szinkronizálandó előzmény", [30, 60, 90, 180, 365, 730, "all"], index=2, format_func=lambda value: "Összes rendelkezésre álló adat" if value == "all" else f"{value} nap")
    history_days = None if history_choice == "all" else int(history_choice)
    force_sync = st.button("Garmin szinkron most", type="primary", use_container_width=True, disabled=demo)
    st.caption("A Garmin-hozzáférés csak olvasási műveleteket használ. Az Összes adat mód lapozott, folytatható backfillt végez; az első futás hosszabb lehet.")

payload = demo_data(history_days or 365) if demo else sync.load_cache()
if force_sync:
    with st.spinner("Garmin-adatok szinkronizálása…"):
        try:
            payload = sync.sync(history_days)
            st.sidebar.success("Szinkron kész")
        except GarminSyncError as exc:
            st.sidebar.error(str(exc))
            payload = sync.load_cache()

if not payload:
    st.warning("Nincs gyorsítótárazott Garmin-adat. Állítsd be a környezeti változókat és indíts kézi szinkront, vagy kapcsold be a bemutató módot.")
    st.stop()

if payload.get("backfill_in_progress"):
    st.warning("A teljes historikus backfill egy korábbi futásban félbeszakadt. A **Garmin szinkron most** gombbal a meglévő cache-től folytathatod.")

stored_checkins = db.list_checkins()
stored_feedback = db.list_feedback()
goals = db.list_goals()
plans = db.list_plans()
checkins = {**payload.get("demo_checkins", {}), **stored_checkins}
feedback = {**payload.get("demo_feedback", {}), **stored_feedback}
wellness, activities = build_daily_frames(payload, feedback)
evaluated_plans = evaluate_training_plans(plans, activities)
today_key = str(wellness.index[-1].date()) if not wellness.empty else date.today().isoformat()
today_checkin = checkins.get(today_key)
readiness = explainable_readiness(wellness, today_checkin, BASELINE_DAYS)

try:
    synced_at = datetime.fromisoformat(payload["synced_at"])
    sync_age = max(0.0, (datetime.now().astimezone() - synced_at).total_seconds() / 3600)
except (KeyError, TypeError, ValueError):
    sync_age = float("inf")
baseline_valid_days = personal_baseline(wellness["hrv"].iloc[:-1], BASELINE_DAYS)["valid_days"] if not wellness.empty else 0
quality = data_quality(wellness.iloc[-1], baseline_valid_days, bool(today_checkin), sync_age) if not wellness.empty else {"score": 0, "level": "alacsony", "missing": ["minden adat"]}
flags = red_flags(wellness, today_checkin, sync_age)
decision = training_decision(readiness, wellness, today_checkin, flags)
plan_guidance = plan_adjustment_message(evaluated_plans)
if plan_guidance.startswith("A közelmúltban magas intenzitású tervet túlteljesítettél"):
    decision["max_intensity"] = "legfeljebb közepes"
    decision["avoid"] = f"{decision['avoid']}; újabb magas intenzitás"
    decision["rules"] = [*decision["rules"], "tervtúlteljesítés-védőkorlát"]
    decision["rationale"] = f"{decision['rationale']}; a legutóbbi magas intenzitású terv túlteljesült."
summary = weekly_summary(wellness, activities, flags)
week_start = str((wellness.index[-1] - timedelta(days=int(wellness.index[-1].weekday()))).date()) if not wellness.empty else str(date.today())
db.save_json("daily_recommendations", "day", today_key, decision)
db.save_json("weekly_summaries", "week_start", week_start, summary)

MODALITY_HU = {"Cardio": "Kardió", "Strength / Functional": "Erő / funkcionális", "Other": "Egyéb"}
LOAD_METHOD_HU = {
    "hr_zones_edwards": "Pulzuszónák (Edwards)", "heart_rate_duration": "Pulzus és idő",
    "duration_intensity": "Idő és intenzitás", "calorie_proxy": "Kalória-proxy",
    "duration_proxy": "Idő-proxy", "session_rpe": "Edzés-RPE",
    "volume_duration": "Volumen és idő",
}
CONFIDENCE_HU = {"high": "magas", "medium": "közepes", "low": "alacsony"}


def hungarian_activity_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    translated = frame.copy()
    if "modality" in translated:
        translated["modality"] = translated["modality"].map(MODALITY_HU).fillna(translated["modality"])
    if "load_method" in translated:
        translated["load_method"] = translated["load_method"].map(LOAD_METHOD_HU).fillna(translated["load_method"])
    if "load_confidence" in translated:
        translated["load_confidence"] = translated["load_confidence"].map(CONFIDENCE_HU).fillna(translated["load_confidence"])
    return translated


def render_checkin(day_key: str) -> None:
    current = checkins.get(day_key, {})
    with st.form(f"checkin-{day_key}"):
        st.markdown("#### Gyors napi check-in")
        a, b = st.columns(2)
        soreness = a.slider("Izomláz", 1, 5, int(current.get("soreness", 2)))
        stress = b.slider("Pszichológiai stressz", 1, 5, int(current.get("stress", 3)))
        motivation = a.slider("Motiváció", 1, 5, int(current.get("motivation", 3)))
        fatigue = b.slider("Általános fáradtság", 1, 5, int(current.get("fatigue", 2)))
        pain_options = ["none", "mild", "significant"]
        pain = st.selectbox("Fájdalom", pain_options, index=pain_options.index(current.get("pain", "none")), format_func={"none":"nincs", "mild":"enyhe", "significant":"jelentős"}.get)
        illness = st.checkbox("Betegségérzet", value=bool(current.get("illness", False)))
        note = st.text_area("Megjegyzés (opcionális)", value=current.get("note", ""))
        if st.form_submit_button("Check-in mentése", type="primary", use_container_width=True):
            db.save_checkin(day_key, soreness=soreness, stress=stress, motivation=motivation, fatigue=fatigue, pain=pain, illness=illness, note=note)
            st.success("A check-in elmentve. Frissítsd az oldalt az új ajánláshoz.")


def render_feedback() -> None:
    if activities.empty:
        st.info("Nincs aktivitás, amelyhez visszajelzést rögzíthetnél.")
        return
    labels = {str(row.activity_id): f"{row.date.date()} · {row['name']} · {row.duration_min:.0f} perc" for _, row in activities.sort_values("date", ascending=False).iterrows()}
    selected = st.selectbox("Aktivitás", list(labels), format_func=labels.get)
    current = feedback.get(selected, {})
    with st.form("session-feedback"):
        rpe = st.slider("Edzés-RPE", 1, 10, int(current.get("rpe", 5)))
        feeling_options = ["easier", "planned", "harder"]
        feeling = st.selectbox("Edzésérzet", feeling_options, index=feeling_options.index(current.get("feeling", "planned")), format_func={"easier":"könnyebb volt", "planned":"terv szerint ment", "harder":"nehezebb volt"}.get)
        focus = st.text_input("Izomcsoport / fókusz", current.get("focus", ""))
        c1, c2, c3 = st.columns(3)
        sets_count = c1.number_input("Sorozatok", 0, 100, int(current.get("sets_count") or 0))
        reps_count = c2.number_input("Ismétlések", 0, 1000, int(current.get("reps_count") or 0))
        volume_kg = c3.number_input("Összvolumen (kg)", 0.0, 100000.0, float(current.get("volume_kg") or 0))
        pack_kg = st.number_input("Hátizsák tömege (kg)", 0.0, 40.0, float(current.get("pack_kg") or 0))
        c4, c5 = st.columns(2)
        stability_min = c4.number_input("Stabilitási munka (perc)", 0, 180, int(current.get("stability_min") or 0))
        single_leg_min = c5.number_input("Egylábas munka (perc)", 0, 180, int(current.get("single_leg_min") or 0))
        note = st.text_area("Megjegyzés", current.get("note", ""))
        if st.form_submit_button("Edzés-visszajelzés mentése", use_container_width=True):
            db.save_feedback(selected, rpe=rpe, feeling=feeling, focus=focus, sets_count=sets_count or None, reps_count=reps_count or None, volume_kg=volume_kg or None, pack_kg=pack_kg or None, stability_min=stability_min or None, single_leg_min=single_leg_min or None, note=note)
            st.success(f"Mentve. Edzésterhelés: {labels[selected].split(' · ')[-1].split()[0]} perc × {rpe} RPE.")


def render_goals_and_plans() -> None:
    st.title("Célok és edzéstervek")
    st.caption("Az eseménycélok irányt adnak, a napi terv pedig összevethető a tényleges Garmin-aktivitással.")
    goal_tab, plan_tab, comparison_tab = st.tabs(["Célok és események", "Edzés tervezése", "Terv és tény"])

    with goal_tab:
        goal_labels = {0: "Új cél létrehozása", **{int(goal["id"]): f"{goal['name']} · {goal.get('event_date') or 'nincs dátum'}" for goal in goals}}
        selected_goal_id = st.selectbox("Szerkesztendő cél", list(goal_labels), format_func=goal_labels.get)
        current_goal = next((goal for goal in goals if int(goal["id"]) == selected_goal_id), {})
        event_types = ["futóverseny", "terepfutás", "magashegyi trekking", "többnapos trekking", "erőcél", "általános hibrid teljesítménycél"]
        rest_days = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]
        with st.form("goal-form"):
            name = st.text_input("Cél vagy esemény neve", current_goal.get("name", ""))
            event_date = st.date_input("Dátum", value=pd.to_datetime(current_goal.get("event_date")).date() if current_goal.get("event_date") else date.today() + timedelta(days=90))
            event_type = st.selectbox("Típus", event_types, index=event_types.index(current_goal.get("event_type", event_types[0])) if current_goal.get("event_type") in event_types else 0)
            c1, c2, c3 = st.columns(3)
            distance_km = c1.number_input("Táv (km)", 0.0, 500.0, float(current_goal.get("distance_km", 0) or 0))
            elevation_m = c2.number_input("Szintemelkedés (m)", 0, 20000, int(current_goal.get("elevation_m", 0) or 0))
            altitude_m = c3.number_input("Várható magasság (m)", 0, 9000, int(current_goal.get("altitude_m", 0) or 0))
            strength_goal = st.text_input("Erőcél", current_goal.get("strength_goal", ""), placeholder="Például: 5 szabályos húzódzkodás")
            c4, c5, c6 = st.columns(3)
            weekly_hours = c4.number_input("Heti rendelkezésre állás (óra)", 1.0, 40.0, float(current_goal.get("weekly_hours", 7) or 7), step=0.5)
            rest_day = c5.selectbox("Preferált pihenőnap", rest_days, index=rest_days.index(current_goal.get("rest_day", "vasárnap")) if current_goal.get("rest_day") in rest_days else 6)
            cardio_target_pct = c6.slider("Cél kardióarány (%)", 0, 100, int(current_goal.get("cardio_target_pct", 60) or 60))
            equipment = st.text_input("Elérhető felszerelés", current_goal.get("equipment", ""), placeholder="Súlyzók, futópad, hátizsák…")
            if st.form_submit_button("Cél mentése", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("A cél neve kötelező.")
                else:
                    db.save_goal(selected_goal_id or None, name=name.strip(), event_date=str(event_date), event_type=event_type, distance_km=distance_km or None, elevation_m=elevation_m or None, altitude_m=altitude_m or None, strength_goal=strength_goal, weekly_hours=weekly_hours, rest_day=rest_day, cardio_target_pct=cardio_target_pct, strength_target_pct=100-cardio_target_pct, equipment=equipment)
                    st.success("A cél elmentve. Frissítsd az oldalt a listához.")
        if selected_goal_id and st.button("Kiválasztott cél törlése", type="secondary"):
            db.delete_goal(selected_goal_id)
            st.success("A cél törölve.")

        if goals:
            st.subheader("Felkészülési állapot")
            goal_rows = []
            for goal in goals:
                analysis = event_preparation_analysis(goal, activities)
                goal_rows.append({"Cél": goal["name"], "Típus": goal["event_type"], "Dátum": goal.get("event_date"), "Hátralévő nap": analysis["days_left"], "Státusz": analysis["status"], "28 nap táv": f"{analysis['distance_28d_km']} km", "28 nap szint": f"{analysis['ascent_28d_m']} m", "Leghosszabb edzés": f"{analysis['longest_session_min']} perc", "Hiányok": "; ".join(analysis["gaps"])})
            st.dataframe(pd.DataFrame(goal_rows), hide_index=True, use_container_width=True)
            recovery = deload_taper_recommendation(wellness, goals, checkins, feedback)
            message = f"**{recovery['type'].capitalize()}** · {recovery['duration_days']} nap · {recovery['reduction_pct']}% volumencsökkentés  \n{recovery['rationale']}  \nAktivált szabályok: {', '.join(recovery['rules'])}"
            (st.warning if recovery["type"] in {"deload", "taper"} else st.info)(message)

    with plan_tab:
        if goals:
            st.subheader("Heti tervsablon")
            template_goal_id = st.selectbox("Sablon célja", [int(goal["id"]) for goal in goals], format_func=lambda value: next(goal["name"] for goal in goals if int(goal["id"]) == value))
            template_start = st.date_input("Hét kezdete", value=date.today() + timedelta(days=(7 - date.today().weekday())), key="template-start")
            template_goal = next(goal for goal in goals if int(goal["id"]) == template_goal_id)
            preview = weekly_plan_template(template_goal, template_start)
            st.dataframe(pd.DataFrame(preview).rename(columns={"planned_date":"Nap","modality":"Modalitás","duration_min":"Perc","intensity":"Intenzitás","purpose":"Cél","target_rpe":"RPE","note":"Megjegyzés"}), hide_index=True, use_container_width=True)
            if st.button("Heti sablon mentése", type="primary"):
                db.save_plans(preview)
                st.success(f"{len(preview)} edzés elmentve. Frissítsd az oldalt a listához.")
            st.divider()
        plan_labels = {0: "Új edzés tervezése", **{int(plan["id"]): f"{plan['planned_date']} · {MODALITY_HU.get(plan['modality'], plan['modality'])} · {plan['duration_min']} perc" for plan in plans}}
        selected_plan_id = st.selectbox("Szerkesztendő terv", list(plan_labels), format_func=plan_labels.get)
        current_plan = next((plan for plan in plans if int(plan["id"]) == selected_plan_id), {})
        modality_options = ["Cardio", "Strength / Functional", "Other"]
        intensity_options = ["könnyű", "közepes", "magas"]
        with st.form("plan-form"):
            planned_date = st.date_input("Tervezett nap", value=pd.to_datetime(current_plan.get("planned_date")).date() if current_plan.get("planned_date") else date.today() + timedelta(days=1), key="planned-date")
            modality_value = st.selectbox("Modalitás", modality_options, index=modality_options.index(current_plan.get("modality", "Cardio")), format_func=MODALITY_HU.get)
            c1, c2, c3 = st.columns(3)
            duration_min = c1.number_input("Időtartam (perc)", 10, 600, int(current_plan.get("duration_min", 60) or 60), step=5)
            intensity = c2.selectbox("Intenzitás", intensity_options, index=intensity_options.index(current_plan.get("intensity", "közepes")))
            target_rpe = c3.slider("Cél-RPE", 1, 10, int(current_plan.get("target_rpe", 5) or 5))
            purpose = st.text_input("Edzés célja", current_plan.get("purpose", ""), placeholder="Zone 2 alapozás, felsőtest-erő…")
            note = st.text_area("Megjegyzés", current_plan.get("note", ""), key="plan-note")
            if st.form_submit_button("Edzésterv mentése", type="primary", use_container_width=True):
                db.save_plan(selected_plan_id or None, planned_date=planned_date, modality=modality_value, duration_min=duration_min, intensity=intensity, purpose=purpose, target_rpe=target_rpe, note=note, matched_activity_id=current_plan.get("matched_activity_id"))
                st.success("Az edzésterv elmentve. Frissítsd az oldalt a listához.")
        if selected_plan_id and st.button("Kiválasztott terv törlése", type="secondary"):
            db.delete_plan(selected_plan_id)
            st.success("Az edzésterv törölve.")

    with comparison_tab:
        if not evaluated_plans:
            st.info("Még nincs összehasonlítható edzésterv.")
        else:
            comparison = pd.DataFrame(evaluated_plans)
            comparison["modality"] = comparison["modality"].map(MODALITY_HU).fillna(comparison["modality"])
            st.dataframe(comparison[["planned_date", "modality", "duration_min", "actual_duration_min", "status", "duration_deviation_min", "match_method"]].rename(columns={"planned_date":"Tervezett nap","modality":"Modalitás","duration_min":"Terv (perc)","actual_duration_min":"Tény (perc)","status":"Státusz","duration_deviation_min":"Eltérés (perc)","match_method":"Párosítás"}), hide_index=True, use_container_width=True)
            st.info(plan_adjustment_message(evaluated_plans))
            plan_to_match = st.selectbox("Kézi párosítás terve", [int(plan["id"]) for plan in plans], format_func=lambda value: next((label for key, label in plan_labels.items() if key == value), str(value)))
            activity_choices = [""] + (activities["activity_id"].astype(str).tolist() if not activities.empty else [])
            activity_label_map = {"": "Automatikus párosítás", **{str(row.activity_id): f"{row.date.date()} · {row['name']} · {row.duration_min:.0f} perc" for _, row in activities.iterrows()}}
            activity_to_match = st.selectbox("Garmin-aktivitás", activity_choices, format_func=activity_label_map.get)
            if st.button("Párosítás mentése"):
                db.match_plan(plan_to_match, activity_to_match or None)
                st.success("A párosítás elmentve.")


def load_chart(prefix: str = "hybrid") -> go.Figure:
    data = wellness.reset_index(names="date")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data["date"], y=data[f"{prefix}_ctl"], name="CTL · τ=42 nap", line=dict(color="#63B3FF", width=3)))
    fig.add_trace(go.Scatter(x=data["date"], y=data[f"{prefix}_atl"], name="ATL · τ=7 nap", line=dict(color="#FF9D72", width=2)))
    fig.add_trace(go.Scatter(x=data["date"], y=data[f"{prefix}_tsb"], name="TSB · előző napi form", line=dict(color="#B39DFF", width=2)))
    fig.add_hline(y=-20, line_dash="dot", line_color="#FF6B6B", annotation_text="óvatossági küszöb")
    fig.update_layout(height=390, margin=dict(l=10, r=10, t=25, b=10), hovermode="x unified", yaxis_title="Személyes terhelési egység")
    return fig


if page == "Ma":
    st.title("Mai edzésdöntés")
    st.caption("Konkrét, determinisztikus ajánlás a személyes alapérték, regeneráció és terhelési előzmény alapján.")
    st.markdown(f"""<div class="decision"><h2>{decision['type']} · {decision['duration']}</h2>
    <p><b>Maximum:</b> {decision['max_intensity']} &nbsp; · &nbsp; <b>Pulzus:</b> {decision['heart_rate_zone']} &nbsp; · &nbsp; <b>RPE:</b> {decision['rpe']}</p>
    <p>{decision['rationale']}</p><p class="muted">Bizonyosság: {decision['confidence']} · Aktivált szabályok: {', '.join(decision['rules'])}</p></div>""", unsafe_allow_html=True)
    st.write("")
    latest = wellness.iloc[-1]
    zone, _ = tsb_zone(float(latest["hybrid_tsb"]))
    cols = st.columns(5)
    cols[0].metric("Edzéskészültség", "—" if readiness.score is None else f"{readiness.score}/100", readiness.confidence)
    cols[1].metric("HRV", "—" if pd.isna(latest.hrv) else f"{latest.hrv:.0f} ms")
    cols[2].metric("RHR", "—" if pd.isna(latest.resting_hr) else f"{latest.resting_hr:.0f} bpm")
    cols[3].metric("Alvás", "—" if pd.isna(latest.sleep_score) else f"{latest.sleep_score:.0f}/100")
    cols[4].metric("Hibrid TSB", f"{latest.hybrid_tsb:+.1f}", zone)
    if flags:
        st.subheader("Kiemelt jelzések")
        for flag in flags:
            (st.error if flag["severity"] == "high" else st.warning if flag["severity"] == "medium" else st.info)(f"**{flag['title']}** — {flag['trigger']}. {flag['action']}")
    if evaluated_plans:
        st.info(f"**Terv–tény visszacsatolás:** {plan_guidance}")
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Mi alakította a pontszámot?")
        st.dataframe(pd.DataFrame(readiness.components).rename(columns={"name":"Komponens","score":"Pont","weight":"Súly %","current":"Aktuális","baseline":"Alapérték","deviation":"Eltérés","interpretation":"Értelmezés"}), hide_index=True, use_container_width=True)
        st.info(f"**Ajánlott:** {decision['type']} vagy {decision['alternative']}  \\n+**Kerüld:** {decision['avoid']}")
    with right:
        render_checkin(today_key)

elif page == "Terhelés és trendek":
    st.title("Terhelés és regeneráció")
    load_label = st.segmented_control("Terhelési dimenzió", ["Hibrid", "Kardió", "Erő / funkcionális"], default="Hibrid")
    load_type = {"Hibrid": "hybrid", "Kardió": "cardio", "Erő / funkcionális": "strength"}.get(load_label or "Hibrid", "hybrid")
    st.plotly_chart(load_chart(load_type), use_container_width=True)
    recent = wellness.reset_index(names="date")
    st.plotly_chart(px.line(recent, x="date", y=["hrv", "resting_hr", "sleep_score"], labels={"value":"Érték", "variable":"Metrika"}), use_container_width=True)
    st.subheader("Aktivitásonkénti terhelési módszer")
    if not activities.empty:
        visible = hungarian_activity_table(activities.sort_values("date", ascending=False))[["date","name","modality","duration_min","cardio_load","strength_load","musculoskeletal_load","lower_body_load","zone2_min","high_intensity_min","load_method","load_confidence"]]
        st.dataframe(visible.rename(columns={"date":"Dátum","name":"Aktivitás","modality":"Modalitás","duration_min":"Időtartam (perc)","cardio_load":"Kardióterhelés","strength_load":"Erőterhelés","musculoskeletal_load":"Mozgásszervi terhelés","lower_body_load":"Alsótest-terhelés","zone2_min":"Zone 2 perc","high_intensity_min":"Magas intenzitású perc","load_method":"Számítási módszer","load_confidence":"Bizonyosság"}), hide_index=True, use_container_width=True)
    st.subheader("Edzés-RPE és visszajelzés")
    render_feedback()

elif page == "Naptár":
    st.title("Edzéstörténeti naptár")
    month = st.date_input("Hónap", value=wellness.index[-1].date())
    start = pd.Timestamp(month).replace(day=1)
    end = start + pd.offsets.MonthEnd()
    calendar_frame = wellness.loc[(wellness.index >= start) & (wellness.index <= end), ["hybrid_load", "hybrid_tsb"]].copy()
    calendar_frame["readiness"] = [explainable_readiness(wellness.loc[:day], checkins.get(str(day.date())), BASELINE_DAYS).score for day in calendar_frame.index]
    calendar_frame["aktivitások"] = activities.groupby("date")["name"].apply(", ".join).reindex(calendar_frame.index, fill_value="") if not activities.empty else ""
    calendar_frame["check-in"] = ["✓" if str(day.date()) in checkins else "—" for day in calendar_frame.index]
    month_calendar = calendar.Calendar(firstweekday=0).monthdayscalendar(start.year, start.month)
    headers = "".join(f'<div class="calendar-head">{name}</div>' for name in ["H", "K", "Sze", "Cs", "P", "Szo", "V"])
    cards = []
    for week in month_calendar:
        for day_number in week:
            if day_number == 0:
                cards.append('<div class="calendar-day empty"></div>')
                continue
            stamp = pd.Timestamp(start.year, start.month, day_number)
            row = calendar_frame.loc[stamp] if stamp in calendar_frame.index else pd.Series(dtype=object)
            activity_names = html.escape(str(row.get("aktivitások", "")))
            readiness_value = row.get("readiness")
            readiness_text = "—" if pd.isna(readiness_value) else f"{readiness_value:.0f}"
            load_value = row.get("hybrid_load")
            load_text = "—" if pd.isna(load_value) else f"{load_value:.0f}"
            today_class = " today" if stamp.date() == date.today() else ""
            check_mark = "✓" if str(stamp.date()) in checkins else ""
            cards.append(f'<div class="calendar-day{today_class}" aria-label="{stamp.date()}"><div class="calendar-number">{day_number} {check_mark}</div><div class="calendar-meta">Készültség: {readiness_text}<br>Terhelés: {load_text}<br>{activity_names or "Pihenő / nincs adat"}</div></div>')
    st.markdown(f'<div class="calendar-grid">{headers}{"".join(cards)}</div>', unsafe_allow_html=True)
    selected_day = st.date_input("Nap részletei", value=wellness.index[-1].date(), min_value=wellness.index.min().date(), max_value=wellness.index.max().date())
    day_activities = activities[activities["date"] == pd.Timestamp(selected_day)] if not activities.empty else activities
    st.dataframe(hungarian_activity_table(day_activities).rename(columns={"date":"Dátum","name":"Aktivitás","modality":"Modalitás","duration_min":"Időtartam (perc)"}), hide_index=True, use_container_width=True)
    render_checkin(str(selected_day))

elif page == "Egyensúly":
    st.title("Kardió–erő egyensúly")
    cutoff = wellness.index[-1] - timedelta(days=27)
    recent = activities[activities["date"] >= cutoff] if not activities.empty else activities
    if recent.empty:
        st.info("Nincs elegendő aktivitás az egyensúly elemzéséhez.")
    else:
        c1, c2, c3 = st.columns(3)
        chart_frame = recent.copy()
        chart_frame["modality"] = chart_frame["modality"].map(MODALITY_HU).fillna(chart_frame["modality"])
        for container, value, title in [(c1,"duration_min","Időarány"),(c2,"cardio_load","Kardióterhelés"),(c3,"activity_id","Alkalmak")]:
            grouped = chart_frame.groupby("modality")[value].count() if value == "activity_id" else chart_frame.groupby("modality")[value].sum()
            container.plotly_chart(px.pie(values=grouped.values, names=grouped.index, hole=.55, title=title), use_container_width=True)
        weekly = chart_frame.assign(week=chart_frame["date"].dt.to_period("W").astype(str)).groupby(["week","modality"])["duration_min"].sum().reset_index()
        st.plotly_chart(px.bar(weekly, x="week", y="duration_min", color="modality", barmode="group", labels={"duration_min":"Perc","week":"Hét","modality":"Modalitás"}), use_container_width=True)

elif page == "Célok és tervek":
    render_goals_and_plans()

elif page == "Mi működik nálam?":
    st.title("Mi működik nálam?")
    st.caption("Retrospektív személyes mintázatok a következő napi HRV és nyugalmi pulzus alapú regenerációval. Kapcsolatot mutat, nem ok-okozatot.")
    patterns = personal_patterns(wellness, activities, feedback)
    progress = min(1.0, patterns["valid_days"] / patterns["minimum_days"])
    st.progress(progress, text=f"Érvényes napok: {patterns['valid_days']} / {patterns['minimum_days']}")
    if patterns["status"] != "ready":
        st.info(patterns["message"])
    else:
        st.info(patterns["message"])
        if patterns["associations"]:
            association_frame = pd.DataFrame(patterns["associations"])
            st.dataframe(association_frame.rename(columns={"factor":"Tényező", "rho":"Spearman ρ", "sample_size":"Mintanagyság", "strength":"Kapcsolat erőssége", "confidence":"Bizonyosság", "statement":"Értelmezés"}), hide_index=True, use_container_width=True)
            st.plotly_chart(px.bar(association_frame, x="factor", y="rho", color="confidence", labels={"factor":"Tényező", "rho":"Rangkorreláció", "confidence":"Bizonyosság"}), use_container_width=True)
        if patterns["modalities"]:
            st.subheader("Modalitás és következő napi regeneráció")
            modality_frame = pd.DataFrame(patterns["modalities"])
            modality_frame["modality"] = modality_frame["modality"].map(MODALITY_HU).fillna(modality_frame["modality"])
            st.dataframe(modality_frame.rename(columns={"modality":"Modalitás", "sample_size":"Mintanagyság", "next_recovery_median":"Regenerációs medián", "confidence":"Bizonyosság"}), hide_index=True, use_container_width=True)
        uncertainty = pattern_uncertainty(wellness, activities, feedback)
        if uncertainty:
            st.subheader("Bizonytalanság és időablak-érzékenység")
            uncertainty_frame = pd.DataFrame([{**item, "window_estimates": ", ".join(f"{window} nap: {value:+.2f}" for window, value in item["window_estimates"].items())} for item in uncertainty])
            st.dataframe(uncertainty_frame.rename(columns={"factor":"Tényező", "ci_low":"Bootstrap alsó 95%", "ci_high":"Bootstrap felső 95%", "stable":"Stabil", "window_estimates":"Időablakok", "window_count":"Ablakok száma", "message":"Minősítés"}), hide_index=True, use_container_width=True)
            stable_items = [item["factor"] for item in uncertainty if item["stable"]]
            if stable_items:
                st.success("**Stabilabb személyes kapcsolatok:** " + ", ".join(stable_items))
            else:
                st.warning("Egyik kapcsolat sem elég stabil ahhoz, hogy több időablakon és a bootstrap-tartomány alapján kiemeljük.")
    st.subheader("Adatminőség és outlierek")
    quality_rows = [{"Metrika": key, "Hiányzó %": patterns["quality"]["missing_pct"].get(key, 0), "Outlierek": patterns["quality"]["outliers"].get(key, 0)} for key in patterns["quality"]["missing_pct"]]
    st.dataframe(pd.DataFrame(quality_rows), hide_index=True, use_container_width=True)
    st.warning("Az eredmény megfigyeléses és zavaró tényezőket tartalmazhat. Ne változtass egyetlen gyenge vagy alacsony bizonyosságú kapcsolat alapján az edzéseden.")

elif page == "Hegyi felkészültség":
    st.title("Hegyi felkészültség")
    mountain_goals = [goal for goal in goals if any(term in goal.get("event_type", "").lower() for term in ("terep", "trek", "hegy"))]
    selected_mountain_goal = st.selectbox("Hegyi cél", [None] + [int(goal["id"]) for goal in mountain_goals], format_func=lambda value: "Általános hegyi felkészültség" if value is None else next(goal["name"] for goal in mountain_goals if int(goal["id"]) == value))
    mountain_goal = next((goal for goal in mountain_goals if int(goal["id"]) == selected_mountain_goal), None)
    mountain = mountain_readiness(activities, feedback, mountain_goal)
    st.metric("Mountain score", "—" if mountain["score"] is None else f"{mountain['score']}/100", mountain["confidence"])
    if mountain["metrics"]:
        labels = {"distance_28d_km":"28 nap táv (km)", "ascent_28d_m":"Szint fel (m)", "descent_28d_m":"Szint le (m)", "longest_day_min":"Leghosszabb nap (perc)", "back_to_back_pairs":"Back-to-back pár", "strength_sessions":"Erőedzés", "pack_sessions":"Hátizsákos alkalom", "max_pack_kg":"Max. hátizsák (kg)"}
        columns = st.columns(4)
        for index, (key, value) in enumerate(mountain["metrics"].items()):
            columns[index % 4].metric(labels[key], value)
    st.subheader("Pontszám összetevői")
    st.dataframe(pd.DataFrame(mountain["components"]).rename(columns={"name":"Komponens", "score":"Pont", "weight":"Súly %"}), hide_index=True, use_container_width=True)
    st.warning("**Fejlesztendő területek:** " + ", ".join(mountain["gaps"]))
    mountain_trends, mountain_warnings = mountain_weekly_trends(activities, feedback)
    st.subheader("Heti hegyi terhelési trend")
    if mountain_trends.empty:
        st.info("Nincs elegendő aktivitás a heti trendhez.")
    else:
        trend_long = mountain_trends.melt(id_vars="week", value_vars=["distance_km", "ascent_m", "descent_m"], var_name="metric", value_name="value")
        trend_long["metric"] = trend_long["metric"].map({"distance_km":"Táv (km)", "ascent_m":"Szint fel (m)", "descent_m":"Szint le (m)"})
        st.plotly_chart(px.line(trend_long, x="week", y="value", color="metric", markers=True, facet_row="metric", labels={"week":"Hét", "value":"Heti érték", "metric":"Metrika"}), use_container_width=True)
        st.plotly_chart(px.bar(mountain_trends, x="week", y="pack_kg_max", labels={"week":"Hét", "pack_kg_max":"Max. hátizsák (kg)"}), use_container_width=True)
    for warning in mountain_warnings:
        st.warning(f"**{warning['title']}** — {warning['detail']}. {warning['action']}")
    multiday = multiday_readiness(activities, wellness, feedback)
    st.subheader("Hosszú és többnapos felkészültség")
    c1, c2, c3 = st.columns(3)
    c1.metric("Többnapos score", f"{multiday['score']}/100", multiday["confidence"])
    c2.metric("120+ perces napok", multiday["metrics"]["long_days_56d"])
    c3.metric("Egymást követő 90+ perces párok", multiday["metrics"]["consecutive_pairs_56d"])
    st.dataframe(pd.DataFrame(multiday["components"]).rename(columns={"name":"Komponens", "score":"Pont", "weight":"Súly %"}), hide_index=True, use_container_width=True)
    st.info(f"**SpO₂-kontextus:** {multiday['spo2_context']}. Ez kizárólag megfigyelési kontextus, nem diagnózis és nem használható önmagában edzésdöntésre.")
    if multiday["gaps"]:
        st.warning("**Többnapos fejlesztendő területek:** " + ", ".join(multiday["gaps"]))
    st.caption("A score sportteljesítményi iránytű: nem jósol célidőt, nem diagnosztizál, és kevés specifikus adatnál csökkenti a bizonyosságot.")

elif page == "Heti jelentés":
    st.title("Heti edzői összefoglaló")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Heti hibrid terhelés", summary["total_load"])
    c2.metric("Változás", "—" if summary["change_pct"] is None else f"{summary['change_pct']:+d}%")
    c3.metric("Erőedzések", summary["strength_sessions"])
    c4.metric("Regeneráló napok", summary["recovery_days"])
    c5, c6 = st.columns(2)
    c5.metric("Zone 2 idő", "Nincs zónaadat" if summary["zone2_min"] is None else f"{summary['zone2_min']} perc")
    c6.metric("Magas intenzitás", "Nincs zónaadat" if summary["high_intensity_min"] is None else f"{summary['high_intensity_min']} perc")
    st.subheader("Következő hét prioritásai")
    for item in summary["recommendations"]:
        st.write(f"- {item}")
    st.plotly_chart(load_chart("hybrid"), use_container_width=True)

else:
    st.title("Beállítások és módszertan")
    st.metric("Adatminőség", f"{quality['score']}/100", quality["level"])
    st.write("**Hiányzó vagy gyenge jelek:**", ", ".join(quality["missing"]) or "nincs")
    st.write(f"**Baseline ablak:** {BASELINE_DAYS} nap (állítsd a `BASELINE_DAYS` változóval, 21–60 nap)")
    st.write(f"**Cache TTL:** {sync.ttl_hours:g} óra · **Cache kor:** {'—' if sync_age == float('inf') else f'{sync_age:.1f} óra'}")
    st.markdown("""
### Rövid módszertan

- A személyes alapérték medián, IQR/MAD és trend alapján készül, legalább 14 érvényes nap alatt instabil jelzéssel.
- Edzéskészültségi súlyok: HRV 25%, alvás/adósság 25%, RHR 15%, terhelés/TSB 15%, előző és sorozatterhelés 10%, manuális wellness 10%. Hiányzó elemnél a súlyok újranormalizálódnak, a bizonyosság csökken.
- ATL és CTL klasszikus exponenciális rekurzió: `alpha = 1 − exp(−1/τ)`, τ=7 és 42 nap. A napi TSB az előző napi CTL−ATL.
- A hibrid terhelés csak személyes gördülő tartományhoz normalizált kardió-, erő- és mozgásszervi komponenseket kombinál.
- Jelentős fájdalom vagy betegségérzet mindig felülírja az intenzív ajánlást.

Ez sportteljesítményi döntéstámogatás, nem orvosi eszköz és nem diagnosztizál.
""")

if payload.get("partial_errors"):
    with st.expander("Részleges Garmin-adathibák"):
        st.write(payload["partial_errors"])
if payload.get("fallback_reason"):
    st.warning(payload["fallback_reason"])
st.caption(f"Adatforrás: {'determinisztikus bemutatóadat' if demo else 'Garmin Connect gyorsítótár'} · Utolsó adatépítés: {payload.get('synced_at', 'ismeretlen')}")
