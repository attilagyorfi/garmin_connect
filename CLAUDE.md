# Hybrid Athlete – fejlesztési útmutató (Claude Code)

Magyar nyelvű edzésdöntés-támogató alkalmazás hibrid sportolóknak (futás, erőedzés, túrázás), Garmin Connect-adatokkal. A felhasználói felület és minden szöveg magyar.

## Felépítés

- `frontend/` – React 19 + Vite egyoldalas alkalmazás (`src/pages/`, `src/components/`, `src/lib/`), Vercelen statikusan kiszolgálva.
- `api/*.py` – Vercel Python-függvények (auth, dashboard, garmin, state, sync, assistant); a logika a gyökérmodulokban van.
- `analytics.py` – determinisztikus elemzőmotor (baseline, terhelés, readiness, napi döntés). Az AI nem számol, csak értelmez.
- `garmin_sync.py`, `garmin_profile.py`, `cloud_sync_job.py` – csak olvasó Garmin-szinkron, folytatható, lépésenkénti felhős backfill.
- `benchmarks.py` (forrásolt korosztályos összevetés), `tips.py` (szabályalapú tippek, heti összefoglaló), `assistant*.py` (Claude-alapú Edzőtárs).
- `evals/assistant/` – az Edzőtárs modell- és prompttesztje szintetikus demóadaton.
- `storage.py` – a szinkron munkakönyvtárának SQLite-tárolója, amelyből a dashboard-összesítés készül. A régi Streamlit/Railway-változatot 2026-10-ben kivezettük; ne hozd vissza.

## Futtatás és ellenőrzés

- Helyi teljes app: lásd README „A React-app helyben” (helyi Postgres a `.local/`-ban, `scripts/dev_api.py`, `npm --prefix frontend run dev`). A szervereket a preview-eszközzel indítsd, ne kérd a felhasználótól.
- Python-tesztek: `python -m pytest -q`; frontend: `npm --prefix frontend run build` és `npm --prefix frontend run test:navigation`.
- A Vercel-függvényeknek csak a `requirements.txt` függőségeivel is importálhatónak kell lenniük (a CI ezt ellenőrzi).
- Valódi Garmin-fiókkal vagy valódi felhasználói adattal tesztelni csak a felhasználó kifejezett kérésére szabad; a böngészős ellenőrzéshez eldobható `@example.test` tesztfiókot és demóadatot (`--seed-demo`) használj, és utána töröld.

## AI

- Minden AI-funkció Claude-ot használ (Anthropic API, `ANTHROPIC_API_KEY`); más szolgáltató nem kerül a kódba.
- Az Edzőtárs modellje `claude-sonnet-5-5` (mért döntés: a Haiku magyarul gyenge). Promptváltoztatás előtt és után futtasd: `python evals/assistant/run_eval.py --prompts`, és csak mért javulást fogadj el.
- A modell csak az `assistant_context.py` által összesített adatot kaphatja: nyers Garmin-adat, jelszó, token, e-mail és azonosító soha.

## Munkamenet

- Minden változás külön ágon készül, PR-ral; a PR-t a felhasználó mergeli. Merge után a helyi `main` frissítése és az ág törlése csak akkor, ha a PR állapota tényleg `MERGED`.
- Commit/PR csak a felhasználó kérésére.

## Szövegezés – természetes magyar

A felület minden szövege olyan legyen, mintha egy jó edző írná, nem gép. Tegeződünk, rövid mondatokban, hétköznapi szavakkal.
- Cselekvő igék, személyesen: „Reggel válaszolj pár kérdésre” – nem „A napi állapotfelmérés kitöltése szükséges”. Szenvedő és hivatalos szerkezet nincs („figyelembe vesszük”, „lehetővé teszi”, „segít abban, hogy”, „biztosítja”, „-ként funkcionál”).
- Egy mondat egy gondolat. Kevés kettőspont és gondolatjel; zárójel csak ritkán.
- Kerülendő töltelék és AI-fordulatok: „egy helyen”, „egy pillantással”, „közérthető”, „átfogó”, „személyre szabott élmény”, „fontos, hogy”, „érdemes megjegyezni”, „ez azt jelenti, hogy”.
- Laikusnak szól: nincs zsargon („forrásolt”, „determinisztikus”, „magyarázható”, „adatlefedettség”, „kohorsz”). Ha egy szakszó kell, egy félmondatban magyarázd meg.
- Angol szó helyett magyar, ahol van jó: readiness → terhelhetőség, Insights → Összefüggések, taper → visszaterhelés. A Garminból ismert rövidítések maradnak (HRV, VO2max, Zone 2, RPE, TSB), első előfordulásnál röviden megmagyarázva.
- Gombfelirat: rövid ige vagy főnév („Mentés”, „Tovább”, „Terv megnyitása”), nem csupa nagybetűs mondat.
- Hibaüzenet: mi történt, és mit tehet a felhasználó, egyszerűen („Nem sikerült menteni. Próbáld újra pár perc múlva.”).

## Felület – tartós design-szabályok

- Elsődleges cél egy kb. 1920 px-es asztali alkalmazás. Kényelmes asztali olvashatóság: törzs- és táblázatszöveg 14–16 px, metaadat legalább 11–12 px, navigáció kb. 16 px, ikonok 22–24 px, elsődleges vezérlők 42–48 px magasak, fő KPI-értékek legalább 21 px. A dashboard használja ki a nézet magasságát; a kártyák legyenek levegősek és áttekinthetők.
- A Hybrid Athlete SVG-jel teljes oldalsávos logóként mindig jól látható, natív 4:3 arányban, olvasható feliratal; összecsukott oldalsávban külön kompakt jel. Onboardingban és belépési állapotokban is ezt a jelet használd, ne helyettesítőt.
- A termék laikusoknak fordítja le a sportadatokat: minden látható KPI-hoz és rövidítéshez közérthető magyar magyarázat kell egérrel és billentyűzetes fókusszal is elérhetően (mit mér, miért fontos, mit jelent a magas/alacsony érték).
- Magyarázatot csak szaggatottan aláhúzott szöveg/érték fölötti tooltip ad. **Kérdőjel-ikon vagy „?” jelvény nem lehet.** Ahol egy sor lenyitható részletezést ad, oda nem kell külön tooltip.
- Akadálymentesség (WCAG 2.1 AA): szöveg sötét kártyán legalább 4,5:1 kontrasztú (a legsötétebb megengedett semleges szürke `#9b9e9c`); minden űrlapmezőnek legyen hozzárendelt címkéje vagy `aria-label`-je, minden ikongombnak neve; a billentyűzetes fókusz mindig látszik. Felugró ablak mindig `.modal-backdrop > .modal` szerkezetű, címmel (`h2`) és `.close` gombbal: a dialógusszerepet, a fókuszkezelést, a Tab-csapdát és az Esc-bezárást a közös `lib/modalA11y.js` adja. A `test:navigation` axe-ellenőrzése (kritikus/súlyos hiba) nem bukhat.
- Az avatar vagy feltöltött profilkép látszik az oldalsávban és a profilösszegzésben, a felhőben mentett profillal együtt; a feltöltött képet mentés előtt kliensoldalon át kell méretezni és tömöríteni.
