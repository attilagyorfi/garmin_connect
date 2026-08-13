"""Streamlit operator UI for explainable hybrid training decisions."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    build_daily_frames, data_quality, explainable_readiness, personal_baseline,
    red_flags, training_decision, tsb_zone, weekly_summary,
)
from garmin_sync import GarminSync, GarminSyncError, demo_data
from storage import Database


st.set_page_config(page_title="Hybrid Training Decision", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1450px; padding-top: 1.4rem}
[data-testid="stMetric"] {background:#151b25; border:1px solid #2c3748; border-radius:12px; padding:14px}
.decision {padding:1.2rem 1.4rem;border-radius:14px;background:linear-gradient(135deg,#14263a,#18201f);border:1px solid #36556f}
.muted {color:#aeb9c8;font-size:.92rem}
@media(max-width:700px){.block-container{padding:0.8rem}.decision{padding:1rem}}
</style>
""", unsafe_allow_html=True)

CACHE_DIR = Path(os.getenv("CACHE_DIR", "data"))
BASELINE_DAYS = int(os.getenv("BASELINE_DAYS", "28"))
db = Database(CACHE_DIR / "training.sqlite3")
sync = GarminSync(CACHE_DIR)

with st.sidebar:
    st.title("HYBRID // COACH")
    page = st.radio("Navigáció", ["Ma", "Terhelés és trendek", "Naptár", "Egyensúly", "Heti jelentés", "Beállítások és módszertan"])
    st.divider()
    demo = st.toggle("Demo mód", value=not bool(os.getenv("GARMIN_EMAIL")), help="Legalább 90 nap determinisztikus mintaadat.")
    history_days = st.select_slider("Előzmény", [30, 60, 90, 120, 180], value=90)
    force_sync = st.button("Garmin szinkron most", type="primary", use_container_width=True, disabled=demo)
    st.caption("A Garmin-hozzáférés csak olvasási műveleteket használ. Az app nem szinkronizál újrarendereléskor.")

payload = demo_data(history_days) if demo else sync.load_cache()
if force_sync:
    with st.spinner("Garmin-adatok szinkronizálása…"):
        try:
            payload = sync.sync(history_days)
            st.sidebar.success("Szinkron kész")
        except GarminSyncError as exc:
            st.sidebar.error(str(exc))
            payload = sync.load_cache()

if not payload:
    st.warning("Nincs cache-elt Garmin-adat. Állítsd be a környezeti változókat és indíts kézi szinkront, vagy kapcsold be a demo módot.")
    st.stop()

stored_checkins = db.list_checkins()
stored_feedback = db.list_feedback()
checkins = {**payload.get("demo_checkins", {}), **stored_checkins}
feedback = {**payload.get("demo_feedback", {}), **stored_feedback}
wellness, activities = build_daily_frames(payload, feedback)
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
summary = weekly_summary(wellness, activities, flags)


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
        rpe = st.slider("Session RPE", 1, 10, int(current.get("rpe", 5)))
        feeling_options = ["easier", "planned", "harder"]
        feeling = st.selectbox("Edzésérzet", feeling_options, index=feeling_options.index(current.get("feeling", "planned")), format_func={"easier":"könnyebb volt", "planned":"terv szerint ment", "harder":"nehezebb volt"}.get)
        focus = st.text_input("Izomcsoport / fókusz", current.get("focus", ""))
        c1, c2, c3 = st.columns(3)
        sets_count = c1.number_input("Sorozatok", 0, 100, int(current.get("sets_count") or 0))
        reps_count = c2.number_input("Ismétlések", 0, 1000, int(current.get("reps_count") or 0))
        volume_kg = c3.number_input("Összvolumen (kg)", 0.0, 100000.0, float(current.get("volume_kg") or 0))
        pack_kg = st.number_input("Hátizsák tömege (kg)", 0.0, 40.0, float(current.get("pack_kg") or 0))
        note = st.text_area("Megjegyzés", current.get("note", ""))
        if st.form_submit_button("Session visszajelzés mentése", use_container_width=True):
            db.save_feedback(selected, rpe=rpe, feeling=feeling, focus=focus, sets_count=sets_count or None, reps_count=reps_count or None, volume_kg=volume_kg or None, pack_kg=pack_kg or None, note=note)
            st.success(f"Mentve. Session load: {labels[selected].split(' · ')[-1].split()[0]} perc × {rpe} RPE.")


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
    st.caption("Konkrét, determinisztikus ajánlás a személyes baseline, regeneráció és terhelési előzmény alapján.")
    st.markdown(f"""<div class="decision"><h2>{decision['type']} · {decision['duration']}</h2>
    <p><b>Maximum:</b> {decision['max_intensity']} &nbsp; · &nbsp; <b>Pulzus:</b> {decision['heart_rate_zone']} &nbsp; · &nbsp; <b>RPE:</b> {decision['rpe']}</p>
    <p>{decision['rationale']}</p><p class="muted">Confidence: {decision['confidence']} · Aktivált szabályok: {', '.join(decision['rules'])}</p></div>""", unsafe_allow_html=True)
    st.write("")
    latest = wellness.iloc[-1]
    zone, _ = tsb_zone(float(latest["hybrid_tsb"]))
    cols = st.columns(5)
    cols[0].metric("Readiness", "—" if readiness.score is None else f"{readiness.score}/100", readiness.confidence)
    cols[1].metric("HRV", "—" if pd.isna(latest.hrv) else f"{latest.hrv:.0f} ms")
    cols[2].metric("RHR", "—" if pd.isna(latest.resting_hr) else f"{latest.resting_hr:.0f} bpm")
    cols[3].metric("Alvás", "—" if pd.isna(latest.sleep_score) else f"{latest.sleep_score:.0f}/100")
    cols[4].metric("Hybrid TSB", f"{latest.hybrid_tsb:+.1f}", zone)
    if flags:
        st.subheader("Kiemelt jelzések")
        for flag in flags:
            (st.error if flag["severity"] == "high" else st.warning if flag["severity"] == "medium" else st.info)(f"**{flag['title']}** — {flag['trigger']}. {flag['action']}")
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Mi alakította a pontszámot?")
        st.dataframe(pd.DataFrame(readiness.components).rename(columns={"name":"Komponens","score":"Pont","weight":"Súly %","current":"Aktuális","baseline":"Baseline","deviation":"Eltérés","interpretation":"Értelmezés"}), hide_index=True, use_container_width=True)
        st.info(f"**Ajánlott:** {decision['type']} vagy {decision['alternative']}  \\n+**Kerüld:** {decision['avoid']}")
    with right:
        render_checkin(today_key)

elif page == "Terhelés és trendek":
    st.title("Terhelés és regeneráció")
    load_type = st.segmented_control("Terhelési dimenzió", ["hybrid", "cardio", "strength"], default="hybrid")
    st.plotly_chart(load_chart(load_type or "hybrid"), use_container_width=True)
    recent = wellness.reset_index(names="date")
    st.plotly_chart(px.line(recent, x="date", y=["hrv", "resting_hr", "sleep_score"], labels={"value":"Érték", "variable":"Metrika"}), use_container_width=True)
    st.subheader("Aktivitásonkénti terhelési módszer")
    if not activities.empty:
        st.dataframe(activities.sort_values("date", ascending=False)[["date","name","modality","duration_min","cardio_load","strength_load","musculoskeletal_load","load_method","load_confidence"]], hide_index=True, use_container_width=True)
    st.subheader("Session RPE és visszajelzés")
    render_feedback()

elif page == "Naptár":
    st.title("Edzéstörténeti naptár")
    month = st.date_input("Hónap", value=wellness.index[-1].date())
    start = pd.Timestamp(month).replace(day=1)
    end = start + pd.offsets.MonthEnd()
    calendar = wellness.loc[(wellness.index >= start) & (wellness.index <= end), ["hybrid_load", "hybrid_tsb"]].copy()
    calendar["readiness"] = [explainable_readiness(wellness.loc[:day], checkins.get(str(day.date())), BASELINE_DAYS).score for day in calendar.index]
    calendar["aktivitások"] = activities.groupby("date")["name"].apply(", ".join).reindex(calendar.index, fill_value="") if not activities.empty else ""
    calendar["check-in"] = ["✓" if str(day.date()) in checkins else "—" for day in calendar.index]
    st.dataframe(calendar.reset_index(names="nap").rename(columns={"hybrid_load":"load","hybrid_tsb":"TSB"}), hide_index=True, use_container_width=True)
    selected_day = st.date_input("Nap részletei", value=wellness.index[-1].date(), min_value=wellness.index.min().date(), max_value=wellness.index.max().date())
    day_activities = activities[activities["date"] == pd.Timestamp(selected_day)] if not activities.empty else activities
    st.dataframe(day_activities, hide_index=True, use_container_width=True)
    render_checkin(str(selected_day))

elif page == "Egyensúly":
    st.title("Cardio–strength egyensúly")
    cutoff = wellness.index[-1] - timedelta(days=27)
    recent = activities[activities["date"] >= cutoff] if not activities.empty else activities
    if recent.empty:
        st.info("Nincs elegendő aktivitás az egyensúly elemzéséhez.")
    else:
        c1, c2, c3 = st.columns(3)
        for container, value, title in [(c1,"duration_min","Időarány"),(c2,"cardio_load","Cardio load"),(c3,"activity_id","Alkalmak")]:
            grouped = recent.groupby("modality")[value].count() if value == "activity_id" else recent.groupby("modality")[value].sum()
            container.plotly_chart(px.pie(values=grouped.values, names=grouped.index, hole=.55, title=title), use_container_width=True)
        weekly = recent.assign(week=recent["date"].dt.to_period("W").astype(str)).groupby(["week","modality"])["duration_min"].sum().reset_index()
        st.plotly_chart(px.bar(weekly, x="week", y="duration_min", color="modality", barmode="group", labels={"duration_min":"Perc"}), use_container_width=True)

elif page == "Heti jelentés":
    st.title("Heti edzői összefoglaló")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Heti hybrid load", summary["total_load"])
    c2.metric("Változás", "—" if summary["change_pct"] is None else f"{summary['change_pct']:+d}%")
    c3.metric("Strength alkalmak", summary["strength_sessions"])
    c4.metric("Regeneráló napok", summary["recovery_days"])
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

- A baseline medián, IQR/MAD és trend alapján készül, legalább 14 érvényes nap alatt instabil jelzéssel.
- Readiness súlyok: HRV 25%, alvás/adósság 25%, RHR 15%, load/TSB 15%, előző és sorozatterhelés 10%, manuális wellness 10%. Hiányzó elemnél a súlyok újranormalizálódnak, a confidence csökken.
- ATL és CTL klasszikus exponenciális rekurzió: `alpha = 1 − exp(−1/τ)`, τ=7 és 42 nap. A napi TSB az előző napi CTL−ATL.
- A Hybrid Load csak személyes gördülő tartományhoz normalizált cardio, strength és musculoskeletal komponenseket kombinál.
- Jelentős fájdalom vagy betegségérzet mindig felülírja az intenzív ajánlást.

Ez sportteljesítményi döntéstámogatás, nem orvosi eszköz és nem diagnosztizál.
""")

if payload.get("partial_errors"):
    with st.expander("Részleges Garmin-adathibák"):
        st.write(payload["partial_errors"])
if payload.get("fallback_reason"):
    st.warning(payload["fallback_reason"])
st.caption(f"Adatforrás: {'deterministic demo' if demo else 'Garmin Connect cache'} · Utolsó adatépítés: {payload.get('synced_at', 'ismeretlen')}")
