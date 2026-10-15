# Hybrid Athlete

Magyar nyelvű, többfelhasználós edzésdöntés-támogató webalkalmazás hibrid sportolóknak (futás, erőedzés, túrázás) Garmin Connect-adatokkal. A fő kérdése: **mit eddzek ma, milyen intenzitással, mennyi ideig és milyen adatok alapján?**

> Sportteljesítményi segédeszköz, nem orvosi eszköz. Nem diagnosztizál és nem helyettesít orvost vagy szakképzett edzőt.

Élesben: React + Vite felület és Vercel Python-függvények, Neon Postgres adatbázissal (`garmin-connect-six.vercel.app`, a `main` ágból automatikusan élesítve).

## Fő funkciók

- zárt, meghívós hozzáférés, önkiszolgáló jelszó-visszaállítás e-mailben, munkamenet-kezelés, adatexport és fióktörlés
- Garmin-kapcsolat titkosított munkamenettokennel (MFA-támogatással), folytatható, teljes történetet visszatöltő felhős szinkron
- determinisztikus elemzőmotor: személyes baseline, terhelés (ATL/CTL/TSB), magyarázható readiness, adatminőség és napi edzésdöntés
- szabályalapú tippek, heti összefoglaló, forrásolt korosztályos összevetés, trendek és fejlődéstörténet
- naptár és edzéstervezés: heti sablon, adaptív újratervezés, terv–tény párosítás
- forrásolt eseményfelkészülési sablonok: maraton–5 km és egynapos/többnapos hegyi túra
- személyes regenerációs modell napi, validált újratanítással
- Claude-alapú Edzőtárs: folyamatos válasz, napi keret, memória és jóváhagyásos tervmódosítás

## Könyvtárstruktúra

```text
frontend/            React 19 + Vite felület (src/pages, src/components, src/lib)
api/                 Vercel Python-függvények (auth, admin, dashboard, garmin, state, sync, assistant, model, retrain)
analytics.py         determinisztikus baseline/terhelés/readiness/döntés
garmin_sync.py       csak olvasó Garmin-lekérés és JSON-cache
cloud_sync_job.py    lépésenkénti, folytatható felhős szinkron
auth_store.py        fiókok, munkamenetek, meghívók, korlátozás
assistant*.py        Edzőtárs (Claude), kontextus, promptok, tervjavaslatok
evals/assistant/     az Edzőtárs modell- és prompttesztje
scripts/             helyi fejlesztői eszközök (dev_api.py, demóadat, Garmin-payload vizsgálat)
tests/               Python-tesztek; a frontend tesztjei a frontend/tests és frontend/scripts alatt
ARCHITECTURE.md      adatfolyam, modulhatárok, biztonság
METHODOLOGY.md       algoritmusok, súlyok, küszöbök és korlátok
ROADMAP.md           elkészült és tervezett fejlesztések
```

## Helyi futtatás

Python 3.12+ és Node 20+ szükséges.

A `scripts/dev_api.py` ugyanazokat az `api/*.py` handlereket szolgálja ki a `127.0.0.1:8765` címen, mint a Vercel; a Vite dev szerver ide proxyzza az `/api` kéréseket. Kell hozzá egy helyi PostgreSQL és egy Gitből kizárt `.env.local`:

```text
DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres
GARMIN_CREDENTIALS_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
HYBRID_ADMIN_EMAILS=<a saját e-mail-címed>
```

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
npm --prefix frontend ci
initdb -D .local/pgdata -U postgres -A trust -E UTF8      # egyszer; a .local/ Gitből kizárt
postgres -D .local/pgdata -p 55432 -c listen_addresses=127.0.0.1
python scripts/dev_api.py
npm --prefix frontend run dev
```

### Zárt hozzáférés és fiókbiztonság

Új fiók csak adminisztrátori meghívóval (`/?invite=…`, 7 napig érvényes, egyszer használható) nyitható. A `HYBRID_ADMIN_EMAILS`-ben felsorolt címek meghívó nélkül is regisztrálhatnak, és admin szerepet kapnak; így hozható létre az első admin. Ha az e-mail-küldés be van állítva (Resend, nem teszt üzemmódban), az új fiók először megerősíti a címét: a regisztráció után 24 óráig érvényes, egyszer használható link megy ki (`/?auth=verify&token=…`), amely be is léptet; megerősítés nélkül a belépés külön hibakódot ad, és a felület felajánlja a levél újraküldését (korlátozott, minden címre ugyanazt válaszolja). E-mail-küldés nélkül (helyi fejlesztés) a regisztráció azonnal megerősít, hogy senki ne rekedjen ki. Elfelejtett jelszónál a felhasználó a belépőoldalon kér visszaállító levelet: aktív fióknál 30 percig érvényes, egyszer használható linket kap (`/?auth=reset&token=…`), a válasz pedig minden címre ugyanaz, így a végpontról nem deríthető ki, kinek van fiókja. A kérések címenként, kliensenként és címenként összesítve is korlátozottak (15 percenként 5). Az admin a Beállítások › Adminisztráció részen a meghívót és a visszaállító linket e-mailben is elküldheti; a link sikertelen küldésnél is kimásolható marad. Az adminisztrátori műveletek naplózódnak.

Az e-maileket a Resend HTTP API-ja küldi (`auth_email.py`, külön függőség nélkül). Élesben ezek a környezeti változók kellenek:

- `RESEND_API_KEY` – a Resend API-kulcsa;
- `AUTH_EMAIL_FROM` – feladó egy a Resendben igazolt domainről, pl. `Hybrid Athlete <noreply@sajatdomain.hu>`;
- `AUTH_PUBLIC_URL` – az alkalmazás nyilvános címe (a levélbeli linkekhez); Vercelen enélkül a projekt éles domainje;
- `AUTH_EMAIL_TEST_MODE` – helyi fejlesztéshez: `1` esetén nem megy ki levél. Élesben ne legyen beállítva.

Az adminoldalon (Beállítások › Adminisztráció) látszik az e-mail-küldés állapota (beállítva / teszt üzemmód / hiányzó kulcs, feladócím), és egy gombbal próbalevél küldhető a saját címre; a Resend hibaüzenete (pl. hibás feladócím-formátum) a hibában is megjelenik. A név nélküli `<cím>` formátumú feladót a kód automatikusan javítja. Ha valaki belépett állapotban nyit meg megerősítő, visszaállító vagy meghívó linket, a felület ezt jelzi, és felajánlja a kijelentkezést, amely után a link automatikusan folytatódik.

A Beállítások › Fiók és biztonság részen kezelhető a jelszócsere (utána minden eszköz kijelentkezik), az aktív munkamenetek, a saját adatok JSON-exportja (`/api/state?export=1`, jelszó, token és Garmin-munkamenet nélkül) és a végleges fióktörlés. A Garmin-kapcsolat csak titkosított munkamenettokent tárol, Garmin-jelszót nem; kétlépcsős (MFA) belépésnél a kódot a felület külön kéri.

Regisztráció után Garmin-fiók nélkül is kipróbálható: `python scripts/dev_api.py --seed-demo <e-mail>` demó dashboardot ment a fiókhoz.

Csatlakoztatott Garmin-fióknál a `python scripts/inspect_garmin_payloads.py <e-mail>` kiírja a sportprofil-végpontok (profil, VO2max, testösszetétel, intenzív percek, lépések, rekordok, erőedzés-sorozatok) válaszainak szerkezetét értékek nélkül, és hogy a `garmin_profile.py` feldolgozói mely mezőket tudták kitölteni.

### Bemutató (onboarding-túra)

Az első belépés utáni beállítóvarázsló végén automatikusan elindul egy lépésenkénti bemutató (`frontend/src/components/GuidedTour.jsx`, lépések: `src/lib/tourSteps.js`): kiemeli az oldalsáv menüpontjait, az Edzőtársat és a Beállításokat, rövid magyar magyarázattal. Saját, függőség nélküli megoldás (a Shepherd.js újabb kiadásai AGPL/kereskedelmi licencűek); a közös dialóguskezelést (`lib/modalA11y.js`) használja: fókusz, Tab-csapda, Esc = kihagyás, nyílbillentyűk. Az állapot a fiókhoz mentődik (`tour`: `pending` → `done`), így megszakítás után a következő belépéskor folytatódik, és eszközfüggetlen. A meglévő felhasználóknál nem indul el magától; a Beállítások › Fiók és biztonság › „Bemutató újraindítása” gombbal bármikor újra megnézhető. Horgonyok: `data-tour` attribútumok; ha egy horgony nincs a lapon (pl. az Edzőtárs az első szinkron előtt), az a lépés kimarad. Nagyobb változásnál a `TOUR_VERSION` emelendő.

### Személyes regenerációs modell (napi karbantartás)

A production telepítés naponta egyszer (03:15 UTC, Vercel Cron) meghívja a `/api/retrain` végpontot. Ehhez a Vercel Production környezetében kötelező egy hosszú, véletlen `CRON_SECRET`; a Vercel ezt `Bearer` hitelesítésként küldi, hiányzó vagy eltérő titoknál a végpont nem indul el.

Az ütemező (`model_registry.py`) futásonként legfeljebb tíz fiókot ellenőriz, felhasználónként elkülönítve. Ugyanazt az adatállapotot nem tanítja újra, és az időrendi validációs kaput nem kerüli meg: gyengébb vagy elégtelen jelöltet eltárol ellenőrzési eredményként, de nem aktivál. Az Insights oldalon (`/api/model`) csak a mintanagyság, az adat-időszak, a lefedettség és a közérthetően magyarázott hibaérték jelenik meg; a modell együtthatói és a nyers Garmin-adatok nem kerülnek a böngészőbe. Fióktörléskor a modellverziók is törlődnek.

### Eseményfelkészülési sablonok

A Cél oldalon a Profilban megadott esemény (maraton, félmaraton, 10 km, 5 km; dátum és opcionális friss verseny- vagy időfutam-eredmény) alapján szakaszolt felkészülési terv készül (`frontend/src/lib/eventTemplates.js`): alapozás, építés, versenyspecifikus szakasz és taper. A kiindulás az elmúlt 4 hét Garmin-futásai; a heti volumen legfeljebb 10%-kal nő, minden negyedik hét könnyebb, a tehermentesítés után a terhelés csak visszatér az előző szintre. A taper a heti volument 41–60%-kal csökkenti megtartott intenzitással (Bosquet és mtsai, 2007; Wang és mtsai, 2023), a hetek túlnyomó része könnyű futás (Seiler, 2010), a tempózónák és a célidő Riegel-formulából (k = 1,06) becsültek. Ha a mostani volumenből a hosszú futás nem éri el a táv szokásos minimumát, a felület ezt kimondja, és rövidebb távot vagy későbbi versenyt javasol. A csúcsvolumen, a hosszú futás felső határa és a négyhetes ritmus edzői gyakorlat, a felület ezt külön jelöli; a források a tervben kattinthatók.

Egynapos hegyi túrára és többnapos, hátizsákos túrára külön sablon készül (`frontend/src/lib/hikeTemplates.js`). A Profilban a túra távja, szintemelkedése, (többnaposnál) a napok száma, a hátizsák súlya és opcionálisan a legmagasabb pont adható meg. A menetidő a DIN 33466 szerint becsült (óránként 300 m fel, 500 m le vagy 4 km), legalább két szintemelkedéssel rögzített Garmin-túra után a saját tempóhoz igazítva. A hosszú edzéstúra hetente legfeljebb 10%-kal nő a túranap kb. 75%-áig, a szint a túra arányát követi, a hátizsák hetente legfeljebb 2 kg-mal nehezedik; többnapos túránál hétvégi, egymást követő túranapok jönnek. Mellette heti két erőedzés és könnyű állóképességi munka (Knapik és mtsai, 2012), lejtmenet-fókuszú túrák (Bontemps és mtsai, 2020) és visszaterhelés; 2500 m felett magassági figyelmeztetés (Luks és mtsai, 2019).

### AI edzőtárs

Az Edzőtárs chat (`api/assistant.py`, `assistant.py`) a Claude Sonnet 5.5 modellt használja; ehhez szerveroldalon `ANTHROPIC_API_KEY` kell (helyben a `.env.local`-ban, élesben a Vercel környezeti változói között). A modell csak az `assistant_context.py` által összesített adatokat kapja. Felhasználónként napi 15 kérdés és napi 150 000 tokenes keret érvényes (budapesti naptári nap szerint). Minden Claude-hívás előtt az `ai_usage.py` felhasználónkénti zár alatt lefoglalja a keretet, utána a tényleges tokenszámmal rögzíti; így párhuzamos kérdések sem léphetik túl a keretet, a sikertelen hívás pedig nem számít bele. Az adminisztrátor a Beállításokban felhasználó nélküli, 30 napos összesítőt lát (kérdések, tokenek, listaáron becsült költség). Mindezek fölött globális havi keret áll (`AI_MONTHLY_BUDGET_USD`, alapból 25 USD, budapesti naptári hónap): 80%-nál az aktív adminok egyszer e-mailt kapnak, 100%-nál az Edzőtárs a hónap végéig szünetel (a felhasználók erről üzenetet látnak, a többi funkció működik), és erről is megy egy levél. A keretellenőrzés globális zár alatt fut; a folyamatban lévő hívások a bemeneti árral számítanak, így az utolsó engedélyezett kérdés legfeljebb egy kérdésnyi összeggel léphet túl. A memória kikapcsolható és törölhető. A válasz folyamatosan, írás közben jelenik meg (NDJSON-stream: `delta` darabok, tervjavaslatnál `reset`, a végén `done` a teljes állapottal); a hozzájárulás-, adat- és keretellenőrzés a stream előtt fut, így ezek hibája sima JSON-válasz marad. Ha a kapcsolat megszakad, a válasz akkor is elkészül, beszámít a keretbe és bekerül a beszélgetésbe.

Az edzőtárs kérésre edzéstervet is javasolhat (`assistant_actions.py`, szigorú sémájú `propose_plan_change` eszköz). A javaslat csak függőben lévő, 24 óráig érvényes művelet: a Naptár kizárólag a felhasználó jóváhagyása után változik, és ha a terv a javaslat óta módosult, a jóváhagyás nem írja felül. A modell a meglévő tervekre rövid jelekkel (T1, T2…) hivatkozik, tárolt azonosítót nem kap.

A modell- és promptteszt szintetikus demóadaton fut: `python evals/assistant/run_eval.py --dry-run` (költségbecslés), `--prompts` (rögzített v1 vs. aktuális prompt), alapból Sonnet 5.5 vs. Haiku 4.5. Az eredmények a Gitből kizárt `evals/assistant/results/` mappába kerülnek.

## Függőségek biztonsága

A `.github/workflows/security-audit.yml` hetente (hétfő 06:00 UTC) és kézzel indítva lefuttatja a `pip-audit`-ot a Python-függőségekre és az `npm audit`-ot a frontendre. Helyben: `pip-audit -r requirements.txt` és `npm --prefix frontend audit`. A `cryptography` a beépített OpenSSL miatt legalább 50-es; az alkalmazás csak a `Fernet` titkosítást használja.

## Környezeti változók

Másold a `.env.example` tartalmát saját, Gitből kizárt `.env` fájlba vagy állítsd be a platformon:

| Változó | Jelentés | Alapérték |
|---|---|---|
| `GARMIN_EMAIL` | Garmin-fiók e-mail – **csak helyi, egyfelhasználós fejlesztői eszközökhöz** | nincs |
| `GARMIN_PASSWORD` | Garmin-jelszó – **csak helyi fejlesztői eszközökhöz** | nincs |
| `CACHE_DIR` | helyi JSON-cache és SQLite könyvtár | `data` |
| `CACHE_TTL_HOURS` | friss cache időtartama | `12` |
| `BASELINE_DAYS` | személyes baseline ablaka | `28` |

Élesben ezeket **ne** állítsd be: ott minden felhasználó a saját, titkosítva tárolt Garmin-munkamenetével szinkronizál, a felhős szinkron (`use_environment=False`) a szerver Garmin-adataira sosem esik vissza.

A `.env`, tokenkönyvtár, cache, SQLite, export és egészségadat Gitből kizárt. A repóba soha ne commitolj valódi hitelesítőt vagy személyes egészségadatot.

## Garmin-szinkron és MFA

Az app kizárólag lekérő metódusokat használ: `get_activities`, `get_activities_by_date`, `get_activity_hr_in_timezones`, `get_hrv_data`, `get_sleep_data`, `get_heart_rates`, `get_morning_training_readiness`, valamint a sportprofil- és erőedzés-végpontok. A szinkron csak a felhasználó gombnyomására fut; rerenderkor nem. Az **Összes rendelkezésre álló adat** mód lapozva lekéri a teljes aktivitástörténetet, a legkorábbi aktivitásig tölti vissza a napi wellness adatokat, 30 naponként részleges cache-t ment, és újrafuttatáskor kihagyja a már cache-elt napokat. Részleges végponthiba nem állítja le a teljes folyamatot, teljes sikertelenségnél pedig az utolsó érvényes cache marad látható. A pulzuszóna-normalizáló anonim, valós eszközszerkezetből készült fixture-ökkel védi az ismert lista-, wrapper-, mapping- és nullaalapú indexváltozatokat; ismeretlen vagy hibás válaszból nem készít kitalált zónaadatot.

A `garminconnect` a Garmin nem hivatalos webes szolgáltatásait használja, ezért API-változás előfordulhat. MFA esetén a kódot a felület külön kéri; a szerver csak a titkosított munkamenettokent tárolja, amely jelszóértékű adat.

## Tesztelés

```bash
python -m pytest -q
npm --prefix frontend run build
npm --prefix frontend run test:unit
npm --prefix frontend run test:navigation
```

A tesztek nem használnak valódi Garmin-fiókot. A `test:navigation` minden oldalon és a szerkesztőablakban axe-core akadálymentességi ellenőrzést is futtat (kritikus vagy súlyos hiba esetén bukik); a színkontrasztot a jsdom nem méri, azt valódi böngészőben ellenőrizzük. A CI ezeken felül ellenőrzi, hogy a Vercel-függvények csak a `requirements.txt` függőségeivel is importálhatók.

## További dokumentáció

- [Architektúra és audit](ARCHITECTURE.md)
- [Módszertan](METHODOLOGY.md)
- [Roadmap és ismert korlátok](ROADMAP.md)
- [Biztonsági mentés és visszaállítás](BACKUP.md)
