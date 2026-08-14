# Módszertan

## Személyes baseline

Az ablak alapértéke 28 nap, 21–60 között konfigurálható. A rendszer mediánt, IQR-t, MAD-ot és lineáris napi trendet számol. A robust z-score: `0.6745 × (x − medián) / MAD`. Legalább 14 érvényes nap alatt a baseline instabil, ezért csökken a confidence. A rendszer nem használ populációs összehasonlítást.

## Load modell

Cardio fallback:

1. Edwards-féle pulzuszóna-perc: `Σ(zóna sorszáma × perc)`;
2. pulzus és idő alapú proxy;
3. idő × explicit intenzitás;
4. kalória proxy;
5. idő proxy.

A Garmin-szinkron a read-only `get_activity_hr_in_timezones` metódussal gazdagítja a kardióaktivitásokat. A normalizáló listás, nested és `zone1`–`zone5` kulcsos válaszokat kezel; ismeretlen formátumnál nem becsül zónát. Zone 2 a második zóna ideje, magas intenzitás a 4–5. zóna összege.

Strength fallback:

1. session load = perc × RPE;
2. volumen és idő;
3. kalória proxy;
4. idő proxy.

Musculoskeletal load a táv, emelkedés, ereszkedés, hosszú időtartam, alsótest-strength és trekking hátizsák súlyából készül. A Hybrid Load a három dimenzió 28 napos személyes mediánjához normalizált indexe: 45% cardio, 35% strength és 20% musculoskeletal. A nyers, eltérő mértékegységeket nem adjuk össze közvetlenül.

## ATL, CTL, TSB

Az exponenciális rekurzió:

```text
alpha = 1 − exp(−1 / tau)
state[t] = state[t−1] + alpha × (load[t] − state[t−1])
```

ATL: τ=7 nap; CTL: τ=42 nap. A napi TSB az előző nap végén ismert `CTL[t−1] − ATL[t−1]`. A kezdeti állapot az első load; 42 nap alatt az értelmezést óvatosan kell kezelni.

## Readiness

| Komponens | Névleges súly |
|---|---:|
| HRV eltérés | 25% |
| alvás és háromnapos alvásadósság | 25% |
| RHR eltérés | 15% |
| Hybrid TSB | 15% |
| előző napi és sorozatterhelés | 10% |
| manuális wellness | 10% |

Hiányzó komponensnél a rendelkezésre álló súlyok 100%-ra normalizálódnak. A komponens pontja, aktuális értéke, baseline-ja, eltérése, tényleges súlya és értelmezése látható. Ezután külön quality/confidence guardrail korlátozza az ajánlás specifikusságát.

## Adatminőség és confidence

A quality pont HRV-t, alvást, RHR-t, aktivitási előzményt, baseline stabilitást, check-int és a sync frissességét értékeli. 80–100 magas, 55–79 közepes, 0–54 alacsony. Alacsony confidence esetén a motor nem ajánl intenzív edzést akkor sem, ha a hiányos readiness magas.

## Döntési szabályok és red flagek

Elsőbbség: betegség → jelentős fájdalom → alacsony confidence → sorozatterhelés/alacsony readiness → magas readiness minőségi nap → közepes readiness Zone 2 → konzervatív technikai strength. Egyetlen gyenge biomarker önmagában nem okoz pihenőnapot.

Figyelmeztetések: háromnapos alacsony HRV, háromnapos baseline+6 bpm RHR, >20% heti load-emelkedés, három egymást követő saját 70. percentilis feletti nap, két egymást követő erős alsótestnap, fájdalom, betegség és 36 óránál régebbi sync. Minden flag adatot, küszöböt és beavatkozást ad.

## Tervezett kontra tényleges edzés

A párosítás sorrendje: kézzel rögzített Garmin-aktivitásazonosító, majd azonos nap és modalitás szerinti első még fel nem használt aktivitás. Időtartamarány alapján 0% elmaradt, 1–74% részben teljesült, 75–125% teljesült, 125% felett túlteljesült. Magas intenzitású terv túlteljesítése a következő ajánlást legfeljebb közepes intenzitásra korlátozza. Több elmaradt edzést a rendszer nem próbál automatikusan bepótoltatni.

## Korlátok

### Mountain score

A 28 napos Mountain score célspecifikus iránytű. Komponensei: táv 20%, szintemelkedés 25%, hosszú nap 20%, egymást követő hosszú napok 15%, lejtmeneti kitettség 10% és erőalap 10%. A cél nélküli nézet konzervatív alapértékeket használ. A confidence a specifikus aktivitások, szintadatok, erőedzések és céladatok lefedettségétől függ. Ez nem célidő-előrejelzés és nem egészségügyi minősítés.

A többnapos score 56 napot vizsgál: a 120 perces hosszú napok és az egymást követő 90 perces napok egyenként 35%, a manuálisan rögzített stabilitási és egylábas munka egyenként 15% súlyt kap. A SpO₂ csak 14 napos medián kontextusként jelenik meg, a score-t és az edzésajánlást nem módosítja.

### Személyes mintázatok

A retrospektív nézet legalább 60 érvényes HRV/RHR napot igényel. A következő napi regenerációs index a HRV pozitív és a nyugalmi pulzus negatív, medián/MAD szerint skálázott eltérése. Az előző napi alvás, HRV, TSB, terhelés és RPE kapcsolatát rangkorrelációval vizsgálja. Minden eredmény mintanagyságot és bizonyosságot kap; az IQR-alapú outlierek és a hiányzások külön jelennek meg. Az eredmény megfigyeléses kapcsolat, nem kauzális bizonyíték.

A stabilitásvizsgálat ugyanazt a kapcsolatot 60, 90 és 120 napos ablakon számolja újra, majd rögzített seed mellett 300 bootstrap mintából 95%-os tartományt képez. Egy kapcsolat csak akkor kap stabil jelzést, ha legalább két időablakban azonos irányú és a bootstrap-tartomány nem metszi a nullát.

A prediktív ellenőrzés legalább 132 célértékes napot igényel. Három időrendhelyes, bővülő tanítóablakot használ; a tesztadat soha nem előzi meg a tanítóadatot. A standardizálás és a hiányzó értékek mediános pótlása foldonként csak a tanítóhalmazon készül. A ridge regresszió a tanító célmedián baseline-nal versenyez. Előrejelzés csak legalább 5% összesített MAE-javulás és legalább két nyertes fold esetén jelenik meg; az intervallum az idősoros tesztmaradékok 10–90. percentilise.

Az algoritmus determinisztikus, de nem klinikailag validált. A wearable adatok mérési hibásak lehetnek; a load proxy nem TSS. A readiness sportdöntési jel, nem betegség- vagy sérülésdiagnózis. A küszöböket hosszabb személyes előtörténettel és edzői visszajelzéssel kell kalibrálni.
