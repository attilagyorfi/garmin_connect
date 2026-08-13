# Roadmap

## Következő P1 finomítások

- aktivitásonkénti pulzuszóna-részletek csak dokumentált `garminconnect` metódussal, fixture-alapú schema-drift tesztekkel
- alsótest-terhelési sorozat és két lower-body nap közötti regeneráció pontosabb jelzése
- Zone 2 és magas intenzitású percek megbízható összesítése
- heti összefoglalók és napi ajánlások automatikus SQLite snapshotja
- valódi havi kártyás naptárkomponens és accessibility audit

## P2 – Célok és tervezés

- esemény/cél CRUD a már létrehozott `goals_events` táblán
- heti rendelkezésre állás, pihenőnap és cardio–strength célarány
- tervezett kontra tényleges edzés és Garmin-aktivitás párosítás
- szabályalapú deload/taper keretek; automatikus teljes edzésterv nélkül

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
- A célkezelő táblaséma kész, a UI és döntési integráció P2.
