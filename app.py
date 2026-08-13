from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import build_daily_frames, coach_insight, readiness, tsb_zone
from garmin_sync import GarminSync, GarminSyncError, demo_data


st.set_page_config(page_title="Hybrid Performance", page_icon="⚡", layout="wide")
st.title("HYBRID // PERFORMANCE")
st.caption("Recovery-aware training load for endurance, strength and mountain work")

with st.sidebar:
    st.header("Data control")
    days = st.radio("History", [30, 60], index=1, horizontal=True)
    demo = st.toggle("Demo data", value=not bool(os.getenv("GARMIN_EMAIL")))
    force_sync = st.button("Sync Garmin now", type="primary", width="stretch", disabled=demo)
    st.caption("Garmin access is read-only. Cached data remains available if a later sync fails.")

sync = GarminSync()
payload = demo_data(days) if demo else sync.load_cache()
if force_sync or (not demo and payload is None):
    with st.spinner("Synchronizing Garmin data…"):
        try:
            payload = sync.sync(days)
            st.sidebar.success("Sync complete")
        except GarminSyncError as exc:
            st.sidebar.error(str(exc))
            payload = sync.load_cache()

if not payload:
    st.warning("No cached Garmin data. Configure credentials and run a sync, or enable Demo data.")
    st.stop()

wellness, activities = build_daily_frames(payload)
score, components, recommendation = readiness(wellness)
latest = wellness.iloc[-1] if not wellness.empty else pd.Series(dtype=float)
tsb = float(latest.get("tsb", 0))
zone, zone_color = tsb_zone(tsb)
hrv = latest.get("hrv")

card1, card2, card3 = st.columns(3)
card1.metric("Today's Readiness", "—" if score is None else f"{score:.0f}/100", recommendation)
card2.metric("Nightly HRV", "—" if pd.isna(hrv) else f"{hrv:.0f} ms")
card3.metric("Training Stress Balance", f"{tsb:+.1f}", zone)

st.subheader("Coach's Insight")
st.info(coach_insight(wellness, score, recommendation), icon="🎯")

left, right = st.columns([2, 1])
with left:
    st.subheader("Load progression")
    load = wellness.reset_index(names="date")
    chart = go.Figure()
    chart.add_trace(go.Scatter(x=load["date"], y=load["ctl"], name="CTL · 42d", line=dict(color="#63B3FF", width=3)))
    chart.add_trace(go.Scatter(x=load["date"], y=load["atl"], name="ATL · 7d", line=dict(color="#FF8A65", width=2)))
    chart.add_trace(go.Scatter(x=load["date"], y=load["tsb"], name="TSB", line=dict(color="#7CFF6B", width=2)))
    chart.add_hline(y=-20, line_dash="dot", line_color="#FF6B6B", annotation_text="Overreaching threshold")
    chart.update_layout(height=410, margin=dict(l=10, r=10, t=20, b=10), hovermode="x unified", yaxis_title="Stress units")
    st.plotly_chart(chart, width="stretch")

with right:
    st.subheader("Modality split")
    if activities.empty:
        st.caption("No activities in the selected range.")
    else:
        split = activities.groupby("modality", as_index=False)["duration_min"].sum()
        donut = px.pie(split, names="modality", values="duration_min", hole=0.68,
                       color="modality", color_discrete_map={"Cardio": "#63B3FF", "Strength / Functional": "#7CFF6B", "Other": "#8892A0"})
        donut.update_traces(textposition="inside", textinfo="percent")
        donut.update_layout(height=410, margin=dict(l=5, r=5, t=20, b=5), showlegend=True)
        st.plotly_chart(donut, width="stretch")

st.subheader("Recovery signals")
signals = wellness.reset_index(names="date")
recovery = go.Figure()
for column, label, color in [("hrv", "HRV (ms)", "#7CFF6B"), ("sleep_score", "Sleep score", "#9C8CFF"), ("resting_hr", "Resting HR", "#FF8A65")]:
    recovery.add_trace(go.Scatter(x=signals["date"], y=signals[column], name=label, line=dict(color=color)))
recovery.update_layout(height=330, margin=dict(l=10, r=10, t=20, b=10), hovermode="x unified")
st.plotly_chart(recovery, width="stretch")

with st.expander("Methodology and data quality"):
    st.markdown(
        """
        - **ATL / CTL:** 7-day and 42-day exponentially weighted averages of activity calories. If calories are absent, duration × 8 is used as a transparent proxy.
        - **TSB:** CTL − ATL. Fresh is above +5, optimal is −20 to +5, and overreaching is below −20.
        - **Readiness:** HRV 40%, sleep 40%, resting HR 20%. Available components are reweighted when a metric is missing.
        - This is a training decision aid, not a medical device. Calibrate thresholds against your own response and coaching context.
        """
    )

synced_at = payload.get("synced_at")
if synced_at:
    try:
        label = datetime.fromisoformat(synced_at).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        label = str(synced_at)
    st.caption(f"Last data build: {label}{' · demo' if payload.get('demo') else ''}")
