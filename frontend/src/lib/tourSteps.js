// The guided tour of the app. Steps point at stable `data-tour` anchors; a step whose anchor is missing (for example
// the coach before the first sync) is skipped. Bump TOUR_VERSION when the tour changes enough to show it again.
export const TOUR_VERSION = 1;

export const TOUR_STEPS = [
  { target: null, title: "Üdv a Hybrid Athlete-ben!", text: "Pár lépésben megmutatjuk, mit hol találsz. A Garmin-adataidból a napi edzésdöntéstől a hosszú távú fejlődésig minden egy helyen van. Bármikor kihagyhatod, és a Beállításokban később újraindíthatod." },
  { target: "nav", title: "Navigáció", text: "Itt éred el az oldalakat. A lakattal jelölt oldalak az első Garmin-szinkron után nyílnak meg, mert a saját adataidból dolgoznak." },
  { target: "Ma", title: "Ma", text: "A napi döntés: mennyire vagy terhelhető ma, és milyen edzés javasolt. A rövid napi állapotfelmérés (fáradtság, izomláz, stressz) is ide kerül, és figyelembe vesszük." },
  { target: "Áttekintés", title: "Áttekintés", text: "A teljesítményképed egy pillantással: terhelés, regeneráció, edzésmennyiség és adatlefedettség, választható időszakra." },
  { target: "Naptár", title: "Naptár", text: "Itt tervezheted az edzéseidet: egyenként, heti sablonnal vagy egy felkészülési tervből. A Garmin-edzéseket automatikusan párosítjuk a tervekkel, így látod, mi valósult meg." },
  { target: "Trendek", title: "Trendek", text: "A hosszabb távú változások: terhelés, HRV, alvás és nyugalmi pulzus. Itt látszik, hogy jó irányba halad-e a formád." },
  { target: "Cél", title: "Cél", text: "A felkészültséged a kitűzött eseményre. Maratontól az 5 km-ig, illetve egynapos vagy többnapos hegyi túrára forrásolt, lépésenkénti felkészülési tervet készítünk." },
  { target: "Insights", title: "Insights", text: "Mi működik nálad? Legalább 60 nap adat után megmutatjuk, mi függ össze a jó napjaiddal, és a személyes regenerációs modell állapotát." },
  { target: "Hol tartasz?", title: "Hol tartasz?", text: "Korosztályos összevetés forrásolt kutatások alapján: például a VO2max-od vagy a nyugalmi pulzusod hogyan viszonyul a veled egykorúakéhoz." },
  { target: "Napló", title: "Napló", text: "Az összes edzésed visszakereshetően. Edzés után itt adhatsz visszajelzést arról, mennyire volt nehéz: ez finomítja a terhelésszámítást." },
  { target: "Profil", title: "Profil", text: "A céljaid, az eseményed, a heti edzésidőd és a pihenőnapod. Ezekből szabjuk személyre a javaslatokat és a terveket." },
  { target: "assistant", title: "Edzőtárs", text: "Kérdezz bármit az edzéseidről: a saját adataidból válaszol. Kérésre tervmódosítást is javasol, de a Naptár csak a jóváhagyásod után változik." },
  { target: "settings", title: "Beállítások", text: "Garmin-kapcsolat, megjelenés, fiók és adatkezelés. Itt indíthatod újra ezt a bemutatót is." },
  { target: null, title: "Kész is vagy!", text: "Ha még nem tetted meg, csatlakoztasd a Garmin-fiókodat, és indítsd el az első szinkront: utána minden oldal a saját adataidból dolgozik." },
];

export function tourAnchor(target) {
  if (!target) return null;
  return [...document.querySelectorAll("[data-tour]")].find(node => node.getAttribute("data-tour") === target) || null;
}

/** The steps that can be shown right now (anchor present, or a centred step). */
export function availableSteps(steps = TOUR_STEPS, find = tourAnchor) {
  return steps.filter(step => !step.target || find(step.target));
}
