# Roadmap

## P0 – Többfelhasználós fiók- és adatszigetelési alap

- elkészült: PostgreSQL-alapú regisztráció és bejelentkezés scrypt jelszóhash-sel
- elkészült: véletlen, lejáró munkamenet HttpOnly + SameSite cookie-ban
- elkészült: profil, terv, check-in, Garmin-cache, dashboard és szinkronállapot elkülönítése `user_id` szerint
- elkészült: felhasználónkénti szinkronzár
- következő: e-mail-megerősítés, jelszó-visszaállítás és belépési próbálkozások korlátozása
- elkészült: felhasználónkénti, Fernet-titkosított Garmin-kapcsolat; a jelszó nem kerül vissza a klienshez
- következő: tartós Garmin-tokenkezelés és MFA bootstrap; addig az MFA-s többfelhasználós Garmin-szinkron nem tekinthető késznek

## P0 – Vercel teljes történeti szinkron

- elkészült: a monolitikus, időtúllépésre érzékeny teljes szinkron felbontása rövid, újraindítható szerverless lépésekre
- elkészült: tartós Neon job-állapot, fázis, százalék, aktivitás-/pulzuszóna-/wellness számlálók és részleges hibák
- elkészült: böngészőből vezérelt folytatás és automatikus újracsatlakozás oldal-újratöltés után
- elkészült: asztali szinkronfolyamat-panel a futó Hybrid Athlete logóval
- következő: Garmin-tokenek titkosított, tartós tárolása és MFA bootstrap folyamat
- következő: valós fiókos, többéves backfill terhelés- és rate-limit teszt Vercelen

## P5 – Személyes AI-asszisztens

- asztali, jobboldali, összecsukható chatpanel beégetett kérdésindítókkal és szabadszavas bevitellel
- felhasználónként elkülönített beszélgetések és törölhető, opcionális beszélgetési memória
- a modell nem kerül egészségadatokkal betanításra; minden válasz jogosultságkezelt, aktuális kontextust kap
- strukturált kontextus: Garmin-idősorok, baseline, readiness, load, terv–tény, check-in, célok és periodizáció
- tudáskontextus: módszertan, mérőszám-definíciók, korlátok és sportbiztonsági szabályok
- a determinisztikus analitikai motor számol; az AI értelmez, összegez és alternatívákat fogalmaz meg
- minden adatállításnál megjeleníthető forrásidőszak és használt mérőszám
- olvasási műveletek alapból engedélyezettek; terv- vagy profilváltoztatás csak előnézet és kifejezett jóváhagyás után
- orvosi diagnózis, sérüléskezelés és indokolatlan kauzális állítás tiltása; piros zászlóknál szakemberhez irányítás
- adatminimalizálás: nyers Garmin payload helyett célzott, összesített kontextus; hitelesítő és token soha nem kerül modellpromptba
- következő: asszisztens API-szerződés, kontextusépítő és jobb oldali desktop chat shell
- következő: modell/provider és költségkorlát kiválasztása, naplózási és adatmegőrzési beállításokkal

## Elkészült üzemi megerősítés

- GitHub Actions CI Python 3.11 és 3.13 alatt, teszt- és szintaxisellenőrzéssel
- letölthető magyar heti jelentés Markdown és JSON formátumban
- részletes szinkron-, adatlefedettségi és modellverzió-állapot
- biztonsági mentési és visszaállítási útmutató

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
- elkészült: a generált napi ajánlások és heti összefoglalók külön historikus UI-ja, grafikonokkal és JSON-exporttal

## Elkészült P2 – Célok és tervezés

- esemény/cél CRUD heti rendelkezésre állással, pihenőnappal és kardió–erő célaránnyal
- napi edzésterv modalitással, idővel, intenzitással, céllal és RPE-vel
- tervezett kontra tényleges edzés automatikus vagy kézi Garmin-aktivitás párosítással
- terveltérés visszacsatolása a következő ajánlásba

## Elkészült P2 tervezési finomítás

- a heti sablon egyedi napkiosztásának, típusának, nevének és időtartamának szerkesztése mentés előtt, kihagyható edzésekkel és napütközés-jelzéssel
- több tervezett edzés együttes mozgatása előre vagy hátra, a heti ritmus megtartásával, dátum-előnézettel és napütközés-védelemmel
- 4/8/12 hetes eseményspecifikus periodizáció alapozó, építő, tehermentesítő, csúcs- és esemény/levezető fázissal; szerkeszthető naptártervek és biztonságos dátumcsere
- adaptív következő heti újratervezés Garmin-teljesítések, tervkövetés, readiness és check-in alapján, magyarázható volumen-/intenzitásváltozással és kihagyott edzések visszasűrítése nélkül

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
- elkészült: foldonkénti feature-együttható-, iránystabilitási és lefedettségi audit
- elkészült: 60+60 napos PSI-, IQR-eltolódás- és missingness-alapú drift-audit
- elkészült: auditálható SQLite modellverziók reprodukálható artifacttal
- elkészült: automatikus aktiválás csak validált és az aktív modellnél jobb MAE-jű jelöltnél
- elkészült: 30 új adatnap, 30 napos modellkor vagy magas drift alapján magyar újratanítási jelzés
- elkészült: aktív modell auditnézet, kétverziós összevetés és megerősített visszaállítás
- következő: opcionális ütemezett újratanítás a telepítési környezet ütemezőjével

## Ismert korlátok

- Az SQLite-adattár egyszemélyes, nincs auth vagy titkosítás.
- A Garmin nem hivatalos web API-ja változhat; nincs élő accountos CI.
- A jelenlegi cardio zóna-load akkor elsődleges, ha a payload már tartalmaz zónaperceket; külön részletlekérés még nincs.
- A demo Mountain példákat ad, de a külön Mountain UI/score P3.
- Az eseményspecifikus periodizáció és a Garmin-tényadatokra reagáló heti adaptáció első szabályalapú változata elkészült; az automatikus alkalmazás továbbra is felhasználói jóváhagyást igényel.
