# Roadmap

## P0 – Többfelhasználós fiók- és adatszigetelési alap

- elkészült: PostgreSQL-alapú regisztráció és bejelentkezés scrypt jelszóhash-sel
- elkészült: véletlen, lejáró munkamenet HttpOnly + SameSite cookie-ban
- elkészült: profil, terv, check-in, Garmin-cache, dashboard és szinkronállapot elkülönítése `user_id` szerint
- elkészült: felhasználónkénti szinkronzár
- elkészült: zárt, admin által létrehozott, egyszer használható meghívó- és jelszó-visszaállító linkek külső e-mail-szolgáltató nélkül
- elkészült: meglévő tag hozzáférésének admin általi felfüggesztése és újraaktiválása; felfüggesztéskor minden munkamenet azonnali visszavonása
- elkészült: adminisztrátori biztonsági napló a meghívókhoz, jelszó-visszaállításhoz és hozzáférésmódosításokhoz, titkos linkek és tokenek tárolása nélkül
- elkészült: öt sikertelen belépés után 15 perces, e-mail- és klienskulcshoz kötött próbálkozáskorlátozás
- elkészült: aktív munkamenetek megtekintése, jelenlegi eszköz jelölése és távoli visszavonása
- elkészült: felhasználónkénti, Fernet-titkosított Garmin-kapcsolat; sikeres hitelesítés után a jelszó nem kerül tárolásra
- elkészült: tartós, titkosított Garmin-tokenkezelés és SQL-ben folytatható, 10 perces MFA bootstrap próbálkozáskorlátozással

## P0 – Vercel teljes történeti szinkron

- elkészült: a monolitikus, időtúllépésre érzékeny teljes szinkron felbontása rövid, újraindítható szerverless lépésekre
- elkészült: tartós Neon job-állapot, fázis, százalék, aktivitás-/pulzuszóna-/wellness számlálók és részleges hibák
- elkészült: böngészőből vezérelt folytatás és automatikus újracsatlakozás oldal-újratöltés után
- elkészült: átmeneti Garmin rate-limit és hálózati hibák fokozatos automatikus újrapróbálása az előrehaladás elvesztése nélkül
- elkészült: a többszöri sikertelen próbálkozás után leállított futás ugyanazzal a futásazonosítóval folytatható
- elkészült: asztali szinkronfolyamat-panel a futó Hybrid Athlete logóval
- elkészült: Garmin-tokenek titkosított, tartós tárolása és MFA bootstrap folyamat
- elkészült: valós fiókos, 379 napos backfill terhelési teszt Vercelen; a böngészőben követett futás megszakítás nélkül befejeződött, és frissítette a dashboardot

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
- elkészült: felhasználónként elkülönített, opcionális és törölhető beszélgetési memória
- elkészült: válaszonkénti adat-időszak és felhasznált mérőszám összefoglaló
- elkészült: módosítási kéréseknél szerveroldalon tárolt előnézet, 24 órás lejárat, külön elutasítás/jóváhagyás és auditált tervmódosítás
- elkészült: környezeti változóval választható AI Gateway modell, válaszonkénti tokenplafon és szerveroldali használati napló
- elkészült: generálásonkénti tartós tokenelszámolás és opcionális díjbecslés, prompttartalom helyett ujjlenyomattal; felhasználónkénti napi tokenkeret, kizárólag szerveroldali írás, párhuzamos kérések zárolása, hiányzó fogyasztásnál megőrzött foglalás és Budapest szerinti napi összesítő
- következő: Vercel-fiókszintű szolgáltatói költségriasztás beállítása a production projektben
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

## P1 megbízhatósági finomítások

- elkészült: 148 valós eszközválasz szerkezeti auditja és személyes értéket nem tartalmazó fixture-készlet; ötzónás lista, üres válasz, nested wrapper, névvel jelölt zóna, perces mezők és nullaalapú `zoneIndex` regressziós védelme
- elkészült: valódi böngészős billentyűzet- és képernyőolvasó-audit; skip link, egységes fókuszjelzés, csökkentett mozgás, elnevezett grafikonok és modális vezérlők
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
- elkészült: napi Vercel Cron által indított, `CRON_SECRET`-tel védett, felhasználónként elkülönített opcionális újratanítás; változatlan adatoknál nem fut újra, és csak az idősoros validációban jobb jelöltet aktiválja
- elkészült: közérthető személyesmodell-állapot az értékelhető napok előrehaladásával, bemeneti adatlefedettséggel, baseline-összevetéssel, időrendi tesztablakokkal és a következő automatikus ellenőrzés idejével

## Ismert korlátok

- A régi, helyi Streamlit/SQLite futtatás továbbra is csak egyszemélyes fejlesztői mód; a production webalkalmazás PostgreSQL-alapú fiók- és adatszigetelést használ.
- A Garmin nem hivatalos web API-ja változhat; nincs élő accountos CI.
- A pulzuszóna-részletek külön Garmin-lekéréssel érkeznek, de az eszköz- és library-verziók közötti payload-eltérések miatt további anonim fixture-validáció szükséges.
- A Mountain readiness elérhető, de pontossága az aktivitástípusok, szintadatok és manuális stabilitási/egylábas bejegyzések lefedettségétől függ.
- Az eseményspecifikus periodizáció és a Garmin-tényadatokra reagáló heti adaptáció első szabályalapú változata elkészült; az automatikus alkalmazás továbbra is felhasználói jóváhagyást igényel.
