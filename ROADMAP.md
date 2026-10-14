# Roadmap

## Következő lépések (2026-10-14)

- Pro előfizetés és fizetés (2 990 Ft/hó vagy 29 900 Ft/év, 14 napos próba) – a felhasználó döntése szerint egyelőre halasztva
- e-mail-cím megerősítése regisztráció után (a háttérfüggvény megvan, levél még nem megy ki)
- valós fiókos, többéves backfill terhelés- és rate-limit teszt Vercelen
- billentyűzetes és képernyőolvasós accessibility audit valódi böngészőben

## Elkészült 2026-10 – Claude-átállás, üzem és bővítések

- minden AI-funkció Claude-alapú (Anthropic API); a korábbi OpenAI/codex-ág teljesen kivezetve, funkciói átültetve (#30–#36)
- Vercel a GitHub-repóhoz kötve, az éles app a `main` ágból automatikusan élesedik
- felhős szinkron kizárólag a felhasználó titkosított Garmin-munkamenetével; a szerver környezeti Garmin-adataira nem esik vissza (#38)
- önkiszolgáló jelszó-visszaállítás és e-mailes meghívó Resenddel, fiókfelderítés elleni semleges válasszal (#40)
- Edzőtárs: folyamatos (streamelt) válasz (#41); eval az éles hívási úton, tervmódosítási esetekkel (#42); v4 prompt – nincs kemény edzés figyelmeztető jelzésnél, tervjavaslat csak kérésre, napnevek a kontextusban, mért átlag 4,33 → 4,46 (#43)
- forrásolt eseményfelkészülési sablonok: maraton–5 km (#37), egynapos hegyi túra és többnapos túra (#44)
- a régi, egyfelhasználós Streamlit/Railway-változat kivezetve (#45)
- globális havi AI-keret (alapból 25 USD): 80%-nál admin-riasztás e-mailben, 100%-nál az Edzőtárs a hónap végéig szünetel

## P0 – Többfelhasználós fiók- és adatszigetelési alap

- elkészült: PostgreSQL-alapú regisztráció és bejelentkezés scrypt jelszóhash-sel
- elkészült: véletlen, lejáró munkamenet HttpOnly + SameSite cookie-ban
- elkészült: profil, terv, check-in, Garmin-cache, dashboard és szinkronállapot elkülönítése `user_id` szerint
- elkészült: felhasználónkénti szinkronzár
- elkészült: jelszó-visszaállítás (adminlink és önkiszolgáló e-mail) és belépési próbálkozások korlátozása
- következő: e-mail-megerősítés regisztráció után
- elkészült: felhasználónkénti, Fernet-titkosított Garmin-kapcsolat; a jelszó nem kerül vissza a klienshez
- elkészült: tartós, Fernet-titkosított Garmin-session tokenek; a szinkronlépések tokennel lépnek be, jelszót csak elutasított token esetén használnak
- elkészült: MFA-s Garmin-belépés: a kódot a felület külön kéri, a szerver csak titkosított munkamenettokent tárol

## P0 – Vercel teljes történeti szinkron

- elkészült: a monolitikus, időtúllépésre érzékeny teljes szinkron felbontása rövid, újraindítható szerverless lépésekre
- elkészült: tartós Neon job-állapot, fázis, százalék, aktivitás-/pulzuszóna-/wellness számlálók és részleges hibák
- elkészült: böngészőből vezérelt folytatás és automatikus újracsatlakozás oldal-újratöltés után
- elkészült: asztali szinkronfolyamat-panel a futó Hybrid Athlete logóval
- elkészült: a lekért rekordok tételenkénti staging táblába kerülnek (`hybrid_sync_items`), a job-állapot nem hordozza a teljes nyers payloadot
- elkészült: MFA bootstrap folyamat
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
- elkészült: Edzőtárs chat (Claude Sonnet 5.5, Anthropic API) összesített kontextussal, hozzájárulással, napi 15 kérdéssel és tokenkerettel, törölhető memóriával
- elkészült: modellválasztás méréssel (30 esetes magyar teszt, Sonnet 5.5 vs Haiku 4.5, promptváltozatok)
- elkészült: jóváhagyásos tervmódosító műveletek (24 órás függő javaslat, T-jeles tervhivatkozás) és admin-oldali, névtelen AI-használatkövetés
- elkészült: folyamatos válasz NDJSON-streammel; megszakadt kapcsolatnál is elkészül és mentődik
- elkészült: eval az éles hívási úton (eszköz, kontextus, magyarázó kör) és v4 prompt méréssel
- elkészült: globális havi költségkeret riasztással és vészfékkel
- következő: Pro csomag (halasztva)

## Elkészült üzemi megerősítés

- GitHub Actions CI Python 3.12 és 3.13 alatt, teszt- és szintaxisellenőrzéssel
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
- elkészült: auditálható modellverziók reprodukálható artifacttal
- elkészült: automatikus aktiválás csak validált és az aktív modellnél jobb MAE-jű jelöltnél
- elkészült: 30 új adatnap, 30 napos modellkor vagy magas drift alapján magyar újratanítási jelzés
- elkészült: aktív modell auditnézet, kétverziós összevetés és megerősített visszaállítás
- elkészült: napi ütemezett újratanítás Vercel Cronnal (`/api/retrain`, 03:15 UTC), validációs kapuval

## Ismert korlátok

- Az AI-költséget felhasználónkénti napi keret és globális havi keret korlátozza; a havi keretet az utolsó engedélyezett kérdés legfeljebb egy kérdésnyi összeggel lépheti túl.
- A Garmin nem hivatalos web API-ja változhat; nincs élő accountos CI.
- A jelenlegi cardio zóna-load akkor elsődleges, ha a payload már tartalmaz zónaperceket; külön részletlekérés még nincs.
- A túrasablon menetideje a DIN 33466 irányértékéből és a saját Garmin-túrák tempójából becsült; terep, időjárás és pihenők nincsenek benne.
- Az eseményspecifikus periodizáció és a Garmin-tényadatokra reagáló heti adaptáció első szabályalapú változata elkészült; az automatikus alkalmazás továbbra is felhasználói jóváhagyást igényel.
