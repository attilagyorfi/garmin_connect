# Hybrid Performance Dashboard

A personal Streamlit dashboard that reads Garmin Connect data, caches it locally, and combines training load with recovery signals.

## Structure

```text
.
├── app.py                  # Streamlit UI and charts
├── analytics.py            # ATL/CTL/TSB, readiness, modality logic
├── garmin_sync.py          # Garmin auth, read-only sync, JSON cache
├── requirements.txt
├── Procfile
├── railway.toml
└── .streamlit/config.toml
```

## Local setup

Python 3.12+ is required by current `garminconnect` releases.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your-password"
streamlit run app.py
```

The app starts in Demo mode when `GARMIN_EMAIL` is absent. Turn Demo mode off and select **Sync Garmin now** for live data. Never commit `.env`, token, cache, or exported health data.

## Railway deployment

1. Create a private GitHub repository and push these files.
2. In Railway, choose **New Project → Deploy from GitHub Repo**.
3. Add service variables `GARMIN_EMAIL`, `GARMIN_PASSWORD`, and `CACHE_DIR=/data`.
4. Add a Railway volume mounted at `/data`; without it, tokens and cache can disappear on redeploy.
5. Deploy. `railway.toml` supplies the start command and health check.

If Garmin requests MFA during initial authentication, the headless deployment cannot answer an interactive prompt. Run one login locally first, or temporarily perform the first sync in an interactive environment, then place the resulting token store on the mounted volume. Treat the token file as a password.

## Vercel note

Streamlit is a persistent Python server, while Vercel's normal runtime is serverless. Railway is the correct fit for this build. A Vercel deployment would require replacing Streamlit with a separate frontend/API architecture and external persistent storage.

## Important limitations

`garminconnect` is an unofficial client for Garmin's web services and may break when Garmin changes private endpoints. Calorie-based stress is useful for trends but is not equivalent to TSS; future calibration should use heart-rate zones, elevation, duration, and strength volume. The recommendations are not medical advice.
