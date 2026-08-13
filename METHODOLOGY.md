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

Figyelmeztetések: háromnapos alacsony HRV, háromnapos baseline+6 bpm RHR, >20% heti load-emelkedés, három egymást követő saját 70. percentilis feletti nap, fájdalom, betegség és 36 óránál régebbi sync. Minden flag adatot, küszöböt és beavatkozást ad.

## Korlátok

Az algoritmus determinisztikus, de nem klinikailag validált. A wearable adatok mérési hibásak lehetnek; a load proxy nem TSS. A readiness sportdöntési jel, nem betegség- vagy sérülésdiagnózis. A küszöböket hosszabb személyes előtörténettel és edzői visszajelzéssel kell kalibrálni.
