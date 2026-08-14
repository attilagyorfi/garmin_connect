# Hybrid Training Decision System

Személyre szabott, magyararázható Streamlit döntéstámogató rendszer futáshoz, strength/functional edzéshez és trekkinghez. A fő kérdése: **mit eddzek ma, milyen intenzitással, mennyi ideig és milyen adatok alapján?**

> Sportteljesítményi segédeszköz, nem orvosi eszköz. Nem diagnosztizál és nem helyettesít orvost vagy szakképzett edzőt.

## Fő funkciók

- 90 napos, determinisztikus demo mód Garmin-fiók nélkül
- kézi, read-only Garmin-szinkron és konfigurálható JSON-cache TTL
- személyes 21–60 napos robusztus baseline (alapérték: 28 nap)
- külön cardio, strength/functional, musculoskeletal és normalizált Hybrid Load
- aktivitásonkénti pulzuszóna-idő, heti Zone 2 és magas intenzitású percek
- alsótest-terhelés és két egymást követő erős alsótestnap regenerációs jelzése
- τ=7 napos ATL, τ=42 napos CTL és előző napi TSB mindhárom fő loadhoz
- 0–100 explainable readiness komponensenkénti ponttal, súllyal és eltéréssel
- adatminőségi pontszám és magas/közepes/alacsony confidence
- konkrét napi edzéstípus, időtartam, pulzuszóna, RPE, alternatíva és kerülendő terhelés
- fájdalom- és betegség-felülbírálás, prioritásos red flagek
- módosítható napi wellness check-in és aktivitásonkénti session RPE
- reszponzív havi kártyás naptár, terhelési trendek, egyensúly és determinisztikus heti összefoglaló
- automatikus napi ajánlás- és heti összefoglaló-snapshot SQLite-ban
- cél- és eseménykezelés heti időkerettel, pihenőnappal és kardió–erő célaránnyal
- napi edzéstervezés, automatikus/kézi Garmin-párosítás és terv–tény visszacsatolás
- verziózott SQLite-séma manuális és generált adatokhoz

## Könyvtárstruktúra

```text
app.py               Streamlit navigáció és UI
analytics.py         tiszta baseline/load/readiness/döntési függvények
garmin_sync.py       read-only Garmin-lekérés és JSON cache
storage.py           verziózott SQLite adattár
tests/               unit-, integrációs és Streamlit AppTest tesztek
ARCHITECTURE.md       adatfolyam, modulhatárok és audit
METHODOLOGY.md        algoritmusok, súlyok, küszöbök és korlátok
ROADMAP.md            a későbbi P2–P4 fejlesztések
```

## Helyi futtatás

Python 3.12+ szükséges.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Hitelesítő adatok nélkül az app automatikusan demo módban indul. A demo 90+ nap konzisztens cardio, strength és trekking adatot, check-int, RPE-t, fáradási és betegségpéldát tartalmaz.

## Környezeti változók

Másold a `.env.example` tartalmát saját, Gitből kizárt `.env` fájlba vagy állítsd be a platformon:

| Változó | Jelentés | Alapérték |
|---|---|---|
| `GARMIN_EMAIL` | Garmin-fiók e-mail | nincs |
| `GARMIN_PASSWORD` | Garmin-jelszó | nincs |
| `CACHE_DIR` | JSON, token és SQLite könyvtár | `data` |
| `CACHE_TTL_HOURS` | friss cache időtartama | `12` |
| `BASELINE_DAYS` | személyes baseline ablaka | `28` |

A `.env`, tokenkönyvtár, cache, SQLite, export és egészségadat Gitből kizárt. A repóba soha ne commitolj valódi hitelesítőt vagy személyes egészségadatot.

## Garmin-szinkron és MFA

Az app kizárólag lekérő metódusokat használ: `get_activities`, `get_activities_by_date`, `get_activity_hr_in_timezones`, `get_hrv_data`, `get_sleep_data`, `get_heart_rates`. A szinkron csak a felhasználó gombnyomására fut; rerenderkor nem. Az **Összes rendelkezésre álló adat** mód lapozva lekéri a teljes aktivitástörténetet, a legkorábbi aktivitásig tölti vissza a napi wellness adatokat, 30 naponként részleges cache-t ment, és újrafuttatáskor kihagyja a már cache-elt napokat. Részleges végponthiba nem állítja le a teljes folyamatot, teljes sikertelenségnél pedig az utolsó érvényes cache marad látható.

A `garminconnect` a Garmin nem hivatalos webes szolgáltatásait használja, ezért API-változás előfordulhat. MFA esetén az első bejelentkezést interaktív helyi környezetben végezd, majd a tokenkönyvtárat biztonságosan tartsd a perzisztens volume-on. A token jelszóértékű adat.

## Railway deployment

1. Deploy from GitHub Repo.
2. Állítsd be a fenti környezeti változókat.
3. Adj Railway volume-ot `/data` mountponttal.
4. Állítsd `CACHE_DIR=/data` értékre.
5. A `railway.toml` és `Procfile` változatlanul Streamlitet indít és health checket ad.

Volume nélkül a token, cache, check-in és RPE új deploynál elveszhet. A Railway marad az elsődleges platform; a projekt nincs Vercelre optimalizálva.

## Adatmodell és manuális bevitel

Az SQLite táblák Garmin-aktivitást, wellness/normalizált napi metrikát, napi check-int, edzés-visszajelzést, célt/eseményt, napi tervet, ajánlást, heti összefoglalót, szinkronmetaadatot és adatminőségi jelzést támogatnak. A `schema_meta` egyszerű verziózást biztosít. A felületen a check-in, edzés-visszajelzés, cél/esemény és napi edzésterv létrehozható, módosítható és törölhető.

Session load: `edzésidő percben × RPE`. Strength/functional aktivitásnál ez elsődleges, ha van RPE.

## Tesztelés

```bash
pytest -q
python -m py_compile app.py analytics.py garmin_sync.py storage.py
```

A tesztek nem használnak valódi Garmin-fiókot. Lefedik a baseline-t, robust z-score-t, load fallbacket, session/musculoskeletal loadot, ATL/CTL/TSB-t, confidence-t, readiness újrasúlyozást, red flageket, biztonsági override-okat, heti összefoglalót, SQLite-ot, cache-t, demo módot és a főképernyő AppTest renderét.

## További dokumentáció

- [Architektúra és audit](ARCHITECTURE.md)
- [Módszertan](METHODOLOGY.md)
- [Roadmap és ismert korlátok](ROADMAP.md)
