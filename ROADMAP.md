# Roadmap

## Elkészült historikus adatkezelés

- korlátlan, lapozott teljes Garmin-aktivitástörténet
- a legkorábbi aktivitásig visszatöltött napi wellness adatok
- folytatható, 30 naponta részleges cache-t mentő backfill
- a már cache-elt napok és HR-zónák ismételt lekérésének elkerülése

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

- több edzés együttes mozgatása
- a heti sablon egyedi napkiosztásának szerkesztése mentés előtt

## Elkészült P2 finomítások

- magyar, szabályalapú deload/taper javaslat aktivált szabályokkal és volumencsökkentéssel
- heti tervsablon a heti időkeret, a kardio–erő arány és a pihenőnap alapján
- eseményspecifikus 28 napos táv-, szint-, hosszú edzés- és erőedzés-hiányok

## P3 – Mountain Readiness

- elkészült: külön mountain score és confidence
- elkészült: 28 napos táv/szint, lejtmeneti kitettség, back-to-back napok és hátizsákos alkalmak
- elkészült: heti trendgrafikonok és progressziós figyelmeztetések
- elkészült: hosszú nap/többnapos readiness, SpO₂ csak nem diagnosztikai kontextusban
- elkészült: manuális stabilitási és egylábas munka rögzítése

## P4 – „Mi működik nálam?”

- elkészült: csak 60+ érvényes napnál induló retrospektív elemzés
- elkészült: mintanagyság és bizonytalanság minden megállapítás mellett
- elkészült: alvás/TSB/RPE/HRV és modalitás rangkorrelációs, nem kauzális elemzése
- elkészült: outlier- és missingness-jelentés
- elkészült: 60/90/120 napos időablak-érzékenység és determinisztikus bootstrap bizonytalansági tartomány
- elkészült: három bővülő idősoros fold, baseline-összevetés és automatikus élesítési kapu
- következő: a valós teljes történet eredménye alapján feature- és drift-audit

## Ismert korlátok

- Az SQLite-adattár egyszemélyes, nincs auth vagy titkosítás.
- A Garmin nem hivatalos web API-ja változhat; nincs élő accountos CI.
- A jelenlegi cardio zóna-load akkor elsődleges, ha a payload már tartalmaz zónaperceket; külön részletlekérés még nincs.
- A demo Mountain példákat ad, de a külön Mountain UI/score P3.
- A cél- és tervkezelés elkészült; eseményspecifikus periodizáció még nincs.
