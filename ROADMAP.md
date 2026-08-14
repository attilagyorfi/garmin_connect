# Roadmap

## Elkészült P1 finomítások

- aktivitásonkénti pulzuszóna-részletek a read-only `get_activity_hr_in_timezones` metódussal és több formátumot lefedő tesztekkel
- alsótest-terhelési sorozat és két erős alsótestnap közötti regenerációs jelzés
- Zone 2 és magas intenzitású percek összesítése, hiányzó zónaadat egyértelmű jelzésével
- heti összefoglalók és napi ajánlások automatikus SQLite-snapshotja
- reszponzív havi kártyás naptár és magyar nyelvű alapfelület

## Következő P1 finomítások

- pulzuszóna-payloadok anonim, valós eszközfixture-ökkel történő további schema-drift validációja
- billentyűzetes és képernyőolvasós accessibility audit valódi böngészőben
- a generált snapshotok külön historikus UI-ja

## Elkészült P2 – Célok és tervezés

- esemény/cél CRUD heti rendelkezésre állással, pihenőnappal és kardió–erő célaránnyal
- napi edzésterv modalitással, idővel, intenzitással, céllal és RPE-vel
- tervezett kontra tényleges edzés automatikus vagy kézi Garmin-aktivitás párosítással
- terveltérés visszacsatolása a következő ajánlásba

## Következő P2 finomítások

- szabályalapú deload/taper keretek; automatikus teljes edzésterv nélkül
- heti tervsablon és több edzés együttes mozgatása
- eseményspecifikus terhelés és hiányzó felkészülési komponensek részletes számítása

## P3 – Mountain Readiness

- külön mountain score és confidence
- heti táv/szint, lejtmeneti excentrikus load, back-to-back napok és hátizsák trend
- hosszú nap/többnapos readiness, SpO₂ csak nem diagnosztikai kontextusban
- manuális stabilitási és egylábas munka rögzítése

## P4 – „Mi működik nálam?”

- csak 60–90+ érvényes napnál induló retrospektív elemzés
- mintanagyság és bizonytalanság minden megállapítás mellett
- alvás/TSB/RPE/HRV és modalitás kapcsolatok robusztus, nem kauzális elemzése
- outlier- és missingness-jelentés; prediktív modell csak megfelelő validációval

## Ismert korlátok

- Az SQLite-adattár egyszemélyes, nincs auth vagy titkosítás.
- A Garmin nem hivatalos web API-ja változhat; nincs élő accountos CI.
- A jelenlegi cardio zóna-load akkor elsődleges, ha a payload már tartalmaz zónaperceket; külön részletlekérés még nincs.
- A demo Mountain példákat ad, de a külön Mountain UI/score P3.
- A cél- és tervkezelés elkészült; eseményspecifikus periodizáció még nincs.
