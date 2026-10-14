# Architektúra

## Adatfolyam

```text
Garmin Connect (csak olvasás) ──> cloud_sync_job (lépésenként, folytatható)
        ▲                                  │  GarminSync: JSON-cache a futás munkakönyvtárában
        │ titkosított munkamenettoken      v
garmin_connection (Postgres)        analytics: normalizálás → terhelés → baseline → readiness → döntés
                                           │  dashboard_api: összesítés, tippek, összevetés
                                           v
                                  Postgres (felhasználónként: dashboard, állapot, tervek)
                                           │
                    api/*.py (Vercel Python-függvények, munkamenet-cookie)
                                           │
                                           v
                                React + Vite felület (frontend/)
                                           │
                       Edzőtárs: assistant_context → Claude (Anthropic API)
```

## Modulok

- `frontend/` – React 19 + Vite egyoldalas alkalmazás; az eseménysablonok (`src/lib/eventTemplates.js`, `src/lib/hikeTemplates.js`) és az időszakos nézetek tiszta függvények, hálózat és tárolás nélkül.
- `api/*.py` – vékony Vercel-handlerek (auth, admin, dashboard, garmin, state, sync, assistant, model, retrain); a logika a gyökérmodulokban van.
- `auth_store.py`, `auth_email.py` – fiókok, munkamenetek, meghívók, jelszó-visszaállítás, korlátozás, adminnapló; tranzakciós e-mail a Resend HTTP API-n.
- `garmin_connection.py`, `garmin_sync.py`, `garmin_profile.py`, `cloud_sync_job.py` – titkosított Garmin-munkamenet, csak olvasó lekérés, folytatható teljes visszatöltés.
- `analytics.py` – mellékhatásmentes normalizálás, baseline, terhelés (ATL/CTL/TSB), readiness, riasztás és napi döntés.
- `dashboard_api.py`, `tips.py`, `benchmarks.py` – a felületnek szóló összesítés, szabályalapú tippek, heti összefoglaló, forrásolt korosztályos összevetés. A `storage.py` a szinkron munkakönyvtárának SQLite-tárolója.
- `user_state.py`, `data_export.py` – felhasználói állapot (profil, check-in, visszajelzés, tervek) validálása, exportja.
- `model_registry.py` – személyes regenerációs modell, időrendi validációs kapuval.
- `assistant.py`, `assistant_context.py`, `assistant_prompts.py`, `assistant_actions.py`, `ai_usage.py` – Claude-alapú Edzőtárs: összesített kontextus, folyamatos válasz, jóváhagyásos tervjavaslat, napi keret és költségnapló.

A determinisztikus motor számol; az AI csak értelmez. A modell kizárólag az `assistant_context.py` által összesített adatot kapja: nyers Garmin-adat, jelszó, token, e-mail és tárolt azonosító nem kerül át.

## Használt Garmin-végpontok

| Kliensmetódus | Cél | Kezelés |
|---|---|---|
| `get_activities` / `get_activities_by_date` | aktivitáslista és összegző mezők (táv, idő, szintemelkedés, terhelés) | lapozott, rendezett időablak, üres lista fallback |
| `get_activity_hr_in_timezones` | aktivitásonkénti pulzuszóna-idő | csak kardiómodalitás, több payload-formátum, hiány megengedett |
| `get_hrv_data` | éjszakai HRV | régi/új kulcsok, hiány megengedett |
| `get_sleep_data` | alváspont és idő | beágyazott payload defenzív olvasása |
| `get_heart_rates` | nyugalmi pulzus | több lehetséges kulcs |
| `get_morning_training_readiness` | Garmin Training Readiness | hiány megengedett |

A csomag nem hivatalos Garmin webes API-kat használ. Író, törlő vagy edzésmódosító metódust az alkalmazás nem hív.

## Adatminőségi kockázatok

- A Garmin payload mezői eszköz, régió és könyvtárverzió szerint eltérhetnek.
- Nem minden eszköz mér HRV-t, alváspontot, pulzuszónát vagy szintemelkedést; a hiány „nincs adat”-ként jelenik meg, nem becsült értékként.
- Rövid előtörténet torzítja a baseline-t és a CTL-t; ezt a bizonyosság (confidence) jelzi.
- A kézi RPE és wellness szubjektív, de az erőedzés terheléséhez fontosabb lehet a kalóriánál.

## Biztonság

- Zárt hozzáférés: új fiók csak meghívóval; jelszó scrypttel, HttpOnly + SameSite=Strict munkamenet-cookie; belépés, visszaállítás és fióktörlés korlátozva.
- A Garmin-kapcsolat csak Fernet-tel titkosított munkamenettokent tárol, Garmin-jelszót nem; a felhős szinkron a szerver környezeti Garmin-adataira sosem esik vissza.
- Felhasználónkénti adatelkülönítés minden táblában; az export jelszót, tokent és Garmin-munkamenetet nem tartalmaz; fióktörléskor az adatok törlődnek, az adminnaplóban csak névtelen nyom marad.
- Az AI-hívásokat felhasználónkénti napi kérdés- és tokenkeret védi, párhuzamos kérésekre is zár alatt.
- Titok csak környezeti változóban (Vercel); a `.env*`, cache, export és egészségadat Gitből kizárt.
