// The guided tour of the app. Steps point at stable `data-tour` anchors; a step whose anchor is missing (for example
// the coach before the first sync) is skipped. Bump TOUR_VERSION when the tour changes enough to show it again.
export const TOUR_VERSION = 1;

export const TOUR_STEPS = [
  { target: null, title: "Szia, üdv a Hybrid Athlete-ben!", text: "Körbevezetünk, pár perc az egész. Bármikor kiléphetsz, és később a Beállításokban újra elindíthatod." },
  { target: "nav", title: "Menü", text: "Innen éred el az oldalakat. Amelyiken lakat van, az az első Garmin-szinkron után nyílik meg, mert a saját adataidból dolgozik." },
  { target: "Ma", title: "Ma", text: "Itt látod, mennyit bírsz ma, és mit érdemes edzeni. Reggel válaszolj a pár rövid kérdésre, és pontosabb lesz a javaslat." },
  { target: "Áttekintés", title: "Áttekintés", text: "Hogy állsz mostanában: mennyit edzettél, mennyire terhelt a szervezeted, és mennyit pihensz. Választhatsz időszakot is." },
  { target: "Naptár", title: "Naptár", text: "Itt tervezed az edzéseidet, egyenként vagy egy egész hétre. A Garmin-edzéseidet magától párosítjuk a tervvel, így látod, mi jött össze." },
  { target: "Trendek", title: "Trendek", text: "Hetek és hónapok alatt hogyan változik a terhelésed, a HRV-d, az alvásod és a nyugalmi pulzusod. Itt látszik, jó irányba haladsz-e." },
  { target: "Cél", title: "Cél", text: "Mennyire állsz készen a versenyedre vagy a túrádra. Maratontól az 5 km-ig és hegyi túrára is hétről hétre felépítjük a felkészülést." },
  { target: "Insights", title: "Összefüggések", text: "Pár hónap adat után megmutatjuk, mitől vannak a jó napjaid: például hogyan hat az alvás vagy a terhelés a formádra." },
  { target: "Hol tartasz?", title: "Hol tartasz?", text: "Hogy állsz a veled egykorúakhoz képest, például VO2max-ban vagy nyugalmi pulzusban. Kutatási adatokkal hasonlítunk." },
  { target: "Napló", title: "Napló", text: "Minden edzésed visszakereshetően. Edzés után írd be, mennyire volt nehéz, így pontosabban számoljuk a terhelést." },
  { target: "Profil", title: "Profil", text: "A célod, a versenyed, és hogy hetente mennyi időd van edzeni. Ezekből szabjuk rád a javaslatokat." },
  { target: "assistant", title: "Edzőtárs", text: "Kérdezz bármit az edzéseidről, a saját adataidból válaszol. Ha kéred, módosít a terveden is, de csak azután, hogy jóváhagytad." },
  { target: "settings", title: "Beállítások", text: "Garmin-kapcsolat, megjelenés, fiók. Itt indíthatod újra ezt a bemutatót is." },
  { target: null, title: "Ennyi volt!", text: "Ha még nem tetted meg, kösd össze a Garmin-fiókodat, és indítsd el az első szinkront. Utána minden oldal a saját adataidból dolgozik." },
];

export function tourAnchor(target) {
  if (!target) return null;
  return [...document.querySelectorAll("[data-tour]")].find(node => node.getAttribute("data-tour") === target) || null;
}

/** The steps that can be shown right now (anchor present, or a centred step). */
export function availableSteps(steps = TOUR_STEPS, find = tourAnchor) {
  return steps.filter(step => !step.target || find(step.target));
}
