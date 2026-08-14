# Architektúra és jelenlegi audit

## Adatfolyam

```text
Garmin Connect (read-only) ──> GarminSync ──> atomic JSON cache
                                              │
Demo generator ───────────────────────────────┤
                                              v
SQLite check-in/RPE ───────────────> normalization + load model
                                              │
                                              v
baseline → data quality → readiness → red flags → daily decision
                                              │
                                              v
                                       Streamlit views
```

## Modulok

- `garmin_sync.py`: autentikáció, explicit kézi szinkron, részleges hibagyűjtés, atomic JSON-cache és determinisztikus demo.
- `storage.py`: kontextuskezelt SQLite-kapcsolat, schema-versioning, check-in és session feedback upsert.
- `analytics.py`: mellékhatásmentes normalizálás, baseline, terhelés, PMC, readiness, riasztás, döntés és heti összefoglaló.
- `app.py`: csak workflow-összeállítás, űrlapok és megjelenítés.

## Használt Garmin-végpontok

| Kliensmetódus | Cél | Kezelés |
|---|---|---|
| `get_activities_by_date` | aktivitáslista és összegző mezők | rendezett időablak, üres lista fallback |
| `get_activity_hr_in_timezones` | aktivitásonkénti pulzuszóna-idő | csak kardiómodalitás, több payload-formátum, hiány megengedett |
| `get_hrv_data` | éjszakai HRV | legacy/current kulcsok, hiány megengedett |
| `get_sleep_data` | alváspont és idő | nested payload defensív olvasása |
| `get_heart_rates` | nyugalmi pulzus | több lehetséges kulcs |

A csomag nem hivatalos Garmin web API-kat használ. Író, törlő vagy edzésmódosító metódust az alkalmazás nem hív.

## Korábbi állapot és javított hiányosságok

A kiinduló prototípus egyetlen kalória/duration proxyt használt; `pandas.ewm(span=7/42)` nem a dokumentált 7/42 napos időállandót adta, a TSB aznapi ATL/CTL-ből készült, és a readiness csak HRV/alvás/RHR volt. Nem volt persistent manuális adat, quality/confidence, red flag, cache TTL vagy biztonsági override. A mostani modulok ezeket elkülönítik és tesztelik.

## Adatminőségi kockázatok

- Garmin payload mezők eszköz, régió és library-verzió szerint eltérhetnek.
- Nem minden eszköz mér HRV-t, alváspontot, pulzuszónát vagy elevation loss-t.
- A Garmin aktivitáslista gyakran csak összegző pulzust ad; ezért a legjobb Edwards-loadhoz további validált zónaadat kell.
- Rövid előtörténet torzítja a baseline-t és CTL-t; ezt stabilitás/confidence jelzi.
- A manuális RPE és wellness szubjektív, de a strength loadhoz fontosabb lehet a kalóriánál.

## Biztonsági kockázatok és kontrollok

- Hitelesítő kizárólag környezeti változóból; placeholderes `.env.example`.
- Token, JSON-cache, SQLite és export Gitből kizárva.
- Atomic cache-csere csökkenti a sérült fájl kockázatát; sikertelen sync nem írja felül a jó cache-t.
- A lokális SQLite nincs titkosítva: a Railway volume és helyi könyvtár hozzáférését korlátozni kell.
- Az alkalmazás egyszemélyes; nincs auth vagy multi-user elkülönítés. Nyilvános deploy előtt platformszintű hozzáférés-védelem szükséges.
