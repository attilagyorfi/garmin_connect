// Event-specific running plans (5 km – marathon). Pure functions: no network, no storage.
// Evidence-based where evidence exists (taper, intensity distribution, race-time prediction); the rest
// (long-run caps, cut-back rhythm, peak volumes) is conventional coaching practice and is labelled as such.

import { isoDate } from "./dates.js";

export const SOURCES = [
  { key: "bosquet2007", label: "Bosquet L, Montpetit J, Arvisais D, Mujika I. Effects of tapering on performance: a meta-analysis. Med Sci Sports Exerc. 2007;39(8):1358–1365.", url: "https://doi.org/10.1249/mss.0b013e31806010e0", claim: "A legjobb eredmény: kb. 2 hetes taper, a volumen fokozatos 41–60%-os csökkentése, az intenzitás és az edzésgyakoriság megtartásával." },
  { key: "wang2023", label: "Wang Z, Wang YT, Gao W, Zhong Y. Effects of tapering on performance in endurance athletes: a systematic review and meta-analysis. PLoS One. 2023;18(5):e0282838.", url: "https://doi.org/10.1371/journal.pone.0282838", claim: "Állóképességi sportolóknál a 41–60%-os volumencsökkentés megtartott intenzitással akár 21 napos taperrel is javította az időfutam-teljesítményt." },
  { key: "seiler2010", label: "Seiler S. What is best practice for training intensity and duration distribution in endurance athletes? Int J Sports Physiol Perform. 2010;5(3):276–291.", url: "https://doi.org/10.1123/ijspp.5.3.276", claim: "Élsportolóknál az edzések kb. 80%-a alacsony intenzitású – ez megfigyelés, nem kötelező arány; mi iránytűként használjuk." },
  { key: "buist2008", label: "Buist I, Bredeweg SW, van Mechelen W, et al. No effect of a graded training program on the number of running-related injuries in novice runners. Am J Sports Med. 2008;36(1):33–39.", url: "https://doi.org/10.1177/0363546507307505", claim: "A „10%-os szabály” szerinti fokozatos program nem csökkentette a sérülések számát kezdő futóknál – nincs bizonyítottan „biztonságos” emelési arány." },
  { key: "nielsen2014", label: "Nielsen RO, Parner ET, Nohr EA, et al. Excessive progression in weekly running distance and risk of running-related injuries. J Orthop Sports Phys Ther. 2014;44(10):739–747.", url: "https://doi.org/10.2519/jospt.2014.5164", claim: "Két hét alatt 30%-nál nagyobb távemelésnél nőhet a távolságfüggő sérülések kockázata (nem szignifikáns, de óvatosságra int)." },
  { key: "riegel1981", label: "Riegel PS. Athletic records and human endurance. American Scientist. 1981;69(3):285–290.", url: "https://www.jstor.org/stable/27850427", claim: "Versenyidő-becslés hatványtörvénnyel (T₂ = T₁·(D₂/D₁)^k); az elterjedt k = 1,06 kerekített érték, a becslés kb. 3,5 perc és 4 óra között megbízható." },
];

const EXPERIENCE_KEYS = ["kezdő", "középhaladó", "haladó"];

// Coaching-practice parameters per event. Peak weekly km and long-run caps are typical recreational ranges.
export const EVENTS = {
  marathon: { label: "Maraton", km: 42.195, weeks: { min: 12, rec: 18, max: 20 }, taper: [0.8, 0.6, 0.45], longCap: 32, longShare: 0.5,
    peakKm: { kezdő: 50, középhaladó: 65, haladó: 80 }, runs: { kezdő: 4, középhaladó: 5, haladó: 6 } },
  half: { label: "Félmaraton", km: 21.0975, weeks: { min: 10, rec: 12, max: 16 }, taper: [0.7, 0.5], longCap: 20, longShare: 0.4,
    peakKm: { kezdő: 35, középhaladó: 45, haladó: 60 }, runs: { kezdő: 3, középhaladó: 4, haladó: 5 } },
  "10k": { label: "10 km", km: 10, weeks: { min: 8, rec: 10, max: 12 }, taper: [0.6], longCap: 16, longShare: 0.35,
    peakKm: { kezdő: 30, középhaladó: 40, haladó: 55 }, runs: { kezdő: 3, középhaladó: 4, haladó: 5 } },
  "5k": { label: "5 km", km: 5, weeks: { min: 6, rec: 8, max: 10 }, taper: [0.6], longCap: 12, longShare: 0.35,
    peakKm: { kezdő: 25, középhaladó: 35, haladó: 50 }, runs: { kezdő: 3, középhaladó: 4, haladó: 5 } },
};
export const EVENT_KEYS = Object.keys(EVENTS);
// Hungarian article + noun for running text ("a maraton", "az 5 km-es verseny").
const PHRASE = { marathon: "a maraton", half: "a félmaraton", "10k": "a 10 km-es verseny", "5k": "az 5 km-es verseny" };
export const RIEGEL_EXPONENT = 1.06;
const MAX_WEEKLY_INCREASE = 0.1; // deliberately conservative; see buist2008/nielsen2014
const CUTBACK_EVERY = 4;
const CUTBACK_FACTOR = 0.8;

const round1 = value => Math.round(value * 10) / 10;
const roundHalf = value => Math.round(value * 2) / 2;

export function inferEventType(profile) {
  if (EVENTS[profile?.eventType]) return profile.eventType;
  const name = String(profile?.eventName || "").toLowerCase();
  if (/f[ée]lmaraton|half/.test(name)) return "half";
  if (/maraton|marathon/.test(name)) return "marathon";
  if (/\b10\s?k(m)?\b/.test(name)) return "10k";
  if (/\b5\s?k(m)?\b/.test(name)) return "5k";
  return null;
}

export function parseRaceTime(text) {
  const parts = String(text || "").trim().split(":").map(Number);
  if (!parts.length || parts.length > 3 || parts.some(part => !Number.isFinite(part) || part < 0)) return null;
  const seconds = parts.reduce((total, part) => total * 60 + part, 0);
  return seconds >= 600 && seconds <= 8 * 3600 ? seconds : null;
}

export function formatDuration(seconds) {
  const total = Math.round(seconds), hours = Math.floor(total / 3600), minutes = Math.floor(total % 3600 / 60), secs = total % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}` : `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function formatPace(secondsPerKm) {
  return `${Math.floor(secondsPerKm / 60)}:${String(Math.round(secondsPerKm % 60)).padStart(2, "0")}/km`;
}

/** Riegel prediction for every event distance plus training paces derived from it. */
export function paceZones(referenceKey, referenceSeconds) {
  const reference = EVENTS[referenceKey];
  if (!reference || !referenceSeconds) return null;
  const predict = km => referenceSeconds * Math.pow(km / reference.km, RIEGEL_EXPONENT);
  const predictions = Object.fromEntries(EVENT_KEYS.map(key => [key, predict(EVENTS[key].km)]));
  const pace = key => predictions[key] / EVENTS[key].km;
  // Threshold ≈ the pace one could hold for about an hour (distance where the predicted time is 60 min).
  const hourKm = reference.km * Math.pow(3600 / referenceSeconds, 1 / RIEGEL_EXPONENT);
  const threshold = 3600 / hourKm;
  return {
    predictions,
    zones: [
      { key: "easy", label: "Könnyű / hosszú futás", from: pace("marathon") * 1.12, to: pace("marathon") * 1.28, note: "Beszélgetős tempó; a heti futás nagy része ide tartozik." },
      { key: "marathon", label: "Maratoni tempó", from: pace("marathon"), to: pace("marathon"), note: "A becsült maratoni versenytempó." },
      { key: "threshold", label: "Küszöbtempó", from: threshold * 0.99, to: threshold * 1.03, note: "Kb. egy órán át tartható, „kényelmesen kemény” tempó." },
      { key: "interval", label: "Intervall (10 km–5 km tempó)", from: pace("5k"), to: pace("10k"), note: "3–5 perces ismétlések, egyenlő pihenővel." },
    ],
  };
}

/** Recent running volume from synced sessions (last 28 days). Missing data stays null. */
export function currentRunning(sessions, today) {
  const end = new Date(`${today}T12:00:00`), start = new Date(end);
  start.setDate(end.getDate() - 27);
  const from = isoDate(start);
  const runs = (sessions || []).filter(item => item?.type === "Futás" && item.date >= from && item.date <= today && Number(item.distanceKm) > 0);
  if (!runs.length) return { weeklyKm: null, longestKm: null, easyPace: null, runs: 0 };
  const total = runs.reduce((sum, item) => sum + Number(item.distanceKm), 0);
  const timed = runs.filter(item => Number(item.durationMin) > 0);
  const paces = timed.map(item => Number(item.durationMin) * 60 / Number(item.distanceKm)).sort((a, b) => a - b);
  return {
    weeklyKm: round1(total / 4), longestKm: round1(Math.max(...runs.map(item => Number(item.distanceKm)))), runs: runs.length,
    // the slower half of recent runs approximates the athlete's easy pace
    easyPace: paces.length ? paces[Math.floor(paces.length * 0.6)] : null,
  };
}

function weeksBetween(fromIso, toIso) {
  return Math.floor((new Date(`${toIso}T12:00:00`) - new Date(`${fromIso}T12:00:00`)) / (7 * 86400000));
}

function mondayOnOrAfter(iso) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + ((8 - date.getDay()) % 7));
  return date;
}

/**
 * Build the plan. Returns { event, weeks, paces, summary, warnings }.
 * Volume grows at most 10% per build week with every 4th week a cut-back, then a taper that keeps intensity.
 */
export function buildEventPlan({ profile, data, eventType, referenceKey, referenceSeconds, today }) {
  const event = EVENTS[eventType];
  if (!event) return null;
  const level = EXPERIENCE_KEYS.includes(profile?.experience) ? profile.experience : "középhaladó";
  const warnings = [];
  const todayIso = today || data?.today || isoDate(new Date());
  const firstMonday = mondayOnOrAfter(todayIso);
  const eventDate = profile?.eventDate && profile.eventDate > todayIso ? profile.eventDate : null;

  let weekCount = event.weeks.rec, start = new Date(firstMonday);
  if (eventDate) {
    const available = weeksBetween(isoDate(firstMonday), eventDate) + 1;
    if (available < event.weeks.min) warnings.push(`Az eseményig ${available} hét van, ${PHRASE[eventType]} szokásos minimális felkészülési ideje ${event.weeks.min} hét. A terv rövidített, ezért óvatosabb célidőt érdemes választani.`);
    weekCount = Math.max(2, Math.min(event.weeks.max, available));
    start = new Date(`${eventDate}T12:00:00`);
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7) - (weekCount - 1) * 7);
    if (available > event.weeks.max) warnings.push(`Az eseményig ${available} hét van; a ${weekCount} hetes célzott terv ${start.toLocaleDateString("hu-HU", { month: "long", day: "numeric" })}-én indul, addig tartsd a mostani, könnyű alapozó futásokat.`);
  } else {
    warnings.push(`Nincs megadva eseménydátum, ezért a javasolt ${weekCount} hetes tervet a következő hétfőtől számoljuk.`);
  }

  const current = currentRunning(data?.sessions, todayIso);
  const peak = event.peakKm[level];
  if (current.weeklyKm == null) warnings.push("Az elmúlt 4 hétből nincs Garmin-futásadat, ezért a kezdő heti volumen a tapasztalati szinted alapján becsült.");
  const startKm = round1(current.weeklyKm != null ? Math.max(current.weeklyKm, 8) : peak * 0.45);
  if (current.weeklyKm != null && current.weeklyKm < peak * 0.35) warnings.push(`A mostani heti futásod (${current.weeklyKm} km) jóval ${PHRASE[eventType]} szokásos csúcsvolumene (${peak} km) alatt van. A terv nem emel hetente 10%-nál többet, ezért a csúcs alacsonyabb maradhat – ez szándékos.`);

  const taperWeeks = Math.min(event.taper.length, Math.max(1, weekCount - 1));
  const buildWeeks = weekCount - taperWeeks;
  const volumes = [];
  let base = startKm;
  for (let index = 0; index < buildWeeks; index += 1) {
    const cutback = (index + 1) % CUTBACK_EVERY === 0 && index < buildWeeks - 1;
    // after a cut-back week the load only returns to the previous level; it grows again a week later
    if (index > 0 && !cutback && !volumes[index - 1].cutback) base = Math.min(peak, base * (1 + MAX_WEEKLY_INCREASE));
    volumes.push({ km: round1(cutback ? base * CUTBACK_FACTOR : base), cutback });
  }
  const peakReached = Math.max(...volumes.map(item => item.km), startKm);
  event.taper.slice(event.taper.length - taperWeeks).forEach(factor => volumes.push({ km: round1(peakReached * factor), taper: true }));

  const longStart = current.longestKm != null ? Math.max(current.longestKm, startKm * 0.3) : startKm * 0.3;
  const paces = paceZones(referenceKey, referenceSeconds);
  const easyPace = paces ? (paces.zones[0].from + paces.zones[0].to) / 2 : current.easyPace || 390;
  if (!paces) warnings.push("Adj meg egy friss verseny- vagy időfutam-eredményt, és személyre szabott tempózónákat számolunk. Addig az időtartamok a Garmin-futásaid átlagtempójából becsültek.");

  const days = (profile?.trainingDays || ["H", "K", "Sze", "Cs", "P", "Szo"]).filter(day => day !== profile?.restDay);
  const strengthCount = Math.min(2, Math.round(days.length * Number(profile?.strengthRatio || 0) / 100));
  const runCount = Math.max(3, Math.min(event.runs[level], days.length - strengthCount));
  const order = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];
  const runDays = [...days].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const longDay = runDays.includes("V") ? "V" : runDays.includes("Szo") ? "Szo" : runDays[runDays.length - 1];

  let longKm = longStart;
  const weeks = volumes.map((volume, index) => {
    const weekStart = new Date(start);
    weekStart.setDate(start.getDate() + index * 7);
    const phaseShare = (index + 1) / buildWeeks;
    const phase = volume.taper ? "Taper" : volume.cutback ? "Tehermentesítés" : phaseShare <= 0.4 ? "Alapozás" : phaseShare <= 0.8 ? "Építés" : "Versenyspecifikus";
    const longCap = Math.min(event.longCap, volume.km * event.longShare);
    if (!volume.taper && !volume.cutback && index > 0) longKm = Math.min(longCap, longKm + 1.5);
    const weekLong = roundHalf(volume.taper ? Math.min(longKm, volume.km * 0.35) : volume.cutback ? Math.min(longKm * 0.75, longCap) : Math.min(longKm, longCap));
    const qualityCount = volume.taper ? 1 : phase === "Alapozás" || volume.cutback ? 1 : 2;
    const sessions = buildWeekSessions({ weekNumber: index + 1, event, eventType, weekStart, volume, weekLong, qualityCount, phase, runCount, runDays, longDay, days, strengthCount: volume.taper ? Math.min(1, strengthCount) : strengthCount, easyPace, paces, eventDate, level });
    const runKm = sessions.filter(item => item.type === "Futás").reduce((sum, item) => sum + (item.km || 0), 0);
    const raceKm = sessions.some(item => item.race) ? event.km : 0;
    const easyKm = sessions.filter(item => item.type === "Futás").reduce((sum, item) => sum + (item.easyKm || 0), 0);
    return { index: index + 1, phase, weekStart: isoDate(weekStart), km: round1(runKm), trainingKm: round1(runKm - raceKm), raceKm, longKm: weekLong, easyShare: runKm - raceKm > 0 ? Math.round(easyKm / (runKm - raceKm) * 100) : null, sessions: sessions.map(({ km, easyKm: _easy, race: _race, ...plan }) => plan) };
  });

  // Coaching practice: a long run of about 75% of the long-run cap (≈24 km for a marathon) before the taper is the
  // usual minimum; if the conservative progression cannot get there, say so plainly instead of pretending.
  const longestPlanned = Math.max(...weeks.map(week => week.longKm));
  const distanceReady = longestPlanned >= event.longCap * 0.75;
  if (!distanceReady) {
    const shorter = { marathon: "félmaratont", half: "10 km-es versenyt", "10k": "5 km-es versenyt", "5k": null }[eventType];
    warnings.unshift(`A mostani futóvolumenedből a heti legfeljebb 10%-os emeléssel a leghosszabb futás csak ${longestPlanned} km-ig jut el, ami kevés ${PHRASE[eventType]} biztonságos teljesítéséhez (kb. ${Math.round(event.longCap * 0.75)} km lenne a minimum). ${shorter ? `Javasoljuk, hogy erre az időpontra ${shorter} válassz, vagy` : "Javasoljuk, hogy"} egy későbbi versenyt célozz meg.`);
  }
  const predicted = paces?.predictions?.[eventType] ?? null;
  return {
    event: { key: eventType, label: event.label, date: eventDate, level },
    weeks, paces, warnings,
    summary: { weeks: weeks.length, distanceReady, startKm, peakKm: Math.max(...weeks.map(week => week.trainingKm)), longestRunKm: Math.max(...weeks.map(week => week.longKm)), taperWeeks, predictedSeconds: predicted, current },
  };
}

function buildWeekSessions({ weekNumber, event, eventType, weekStart, volume, weekLong, qualityCount, phase, runCount, runDays, longDay, days, strengthCount, easyPace, paces, eventDate, level }) {
  const dateOf = code => { const date = new Date(weekStart); date.setDate(weekStart.getDate() + ["H", "K", "Sze", "Cs", "P", "Szo", "V"].indexOf(code)); return isoDate(date); };
  const zone = key => paces?.zones.find(item => item.key === key);
  const paceText = key => { const item = zone(key); return item ? (item.from === item.to ? formatPace(item.from) : `${formatPace(item.from)}–${formatPace(item.to)}`) : null; };
  const minutes = (km, factor = 1) => Math.max(20, Math.round(km * easyPace * factor / 60 / 5) * 5);
  const others = runDays.filter(code => code !== longDay);
  // spread quality days: first and middle of the remaining run days, never the day before the long run
  // Low volume means fewer, shorter runs: fixed minimum lengths would silently double a beginner's week.
  const runsThisWeek = Math.max(3, Math.min(runCount, Math.floor(volume.km / 5)));
  const qualityDays = others.filter((code, index) => index === 0 || index === Math.floor(others.length / 2)).slice(0, Math.min(qualityCount, Math.max(1, runsThisWeek - 3))); // ≤4 runs: one key session, so the week stays mostly easy
  const easyDays = others.filter(code => !qualityDays.includes(code)).slice(0, Math.max(0, runsThisWeek - 1 - qualityDays.length));
  const qualityKm = Math.max(Math.min(6, volume.km * 0.25), Math.min(14, volume.km * 0.18));
  const easyKm = Math.max(2, (volume.km - weekLong - qualityKm * qualityDays.length) / Math.max(1, easyDays.length));
  const sessions = [];
  const specific = { marathon: ["Maratoni tempójú futás", "marathon"], half: ["Küszöbfutás", "threshold"], "10k": ["Intervallfutás", "interval"], "5k": ["Intervallfutás", "interval"] }[eventType];

  qualityDays.forEach((code, index) => {
    const km = roundHalf(volume.taper ? qualityKm * 0.7 : qualityKm);
    let title, zoneKey, detail;
    if (phase === "Alapozás" || volume.cutback) {
      [title, zoneKey, detail] = ["Könnyű futás + 6–8 rövid gyorsítás", "easy", "20 mp-es laza gyorsítások teljes pihenővel; a technikát és a futógazdaságosságot fejleszti."];
    } else if (volume.taper) {
      [title, zoneKey, detail] = ["Rövid versenytempós blokk", eventType === "marathon" ? "marathon" : eventType === "half" ? "threshold" : "interval", "Kevesebb ismétlés, változatlan intenzitás – a taper lényege."];
    } else if (index === 0) {
      [title, zoneKey, detail] = ["Küszöbfutás", "threshold", level === "kezdő" ? "3×8 perc küszöbtempó 2 perc kocogással." : "3×10–12 perc küszöbtempó 2 perc kocogással."];
    } else {
      [title, zoneKey] = specific;
      detail = eventType === "marathon" ? `${Math.round(km * 0.6)} km maratoni tempóban a futás közepén.` : eventType === "half" ? "2×15–20 perc küszöbtempó." : eventType === "10k" ? "5–6×1000 m 10 km-es tempóban, 2–3 perc kocogással." : "6–8×400–600 m 5 km-es tempóban, egyenlő pihenővel.";
    }
    const pace = paceText(zoneKey);
    // warm-up, cool-down and recoveries are easy running; only the work portion counts as hard
    const workShare = zoneKey === "easy" ? 0 : zoneKey === "marathon" ? 0.6 : 0.45;
    sessions.push({ km, easyKm: km * (1 - workShare), date: dateOf(code), type: "Futás", title: `${title} · ${km} km`, duration: minutes(km, zoneKey === "easy" ? 1 : 0.92),
      intensity: zoneKey === "easy" ? "könnyű–közepes" : "közepes–magas", rpe: zoneKey === "easy" ? 4 : 7, purpose: `${event.label} · ${phase.toLowerCase()}`,
      note: [detail, pace && `Tempó: ${pace}.`, "Bemelegítés és levezetés 10–15 perc könnyű futással."].filter(Boolean).join(" ") });
  });
  easyDays.forEach(code => {
    const km = roundHalf(easyKm);
    sessions.push({ km, easyKm: km, date: dateOf(code), type: "Futás", title: `Könnyű futás · ${km} km`, duration: minutes(km), intensity: "könnyű", rpe: 3,
      purpose: `${event.label} · ${phase.toLowerCase()}`, note: [`Beszélgetős tempó${paceText("easy") ? ` (${paceText("easy")})` : ""}.`, "Ha fáradt vagy, rövidítsd – a könnyű nap a regenerációt szolgálja."].join(" ") });
  });
  const isRaceWeek = eventDate && dateOf("H") <= eventDate && eventDate <= dateOf("V");
  if (isRaceWeek) {
    sessions.push({ km: event.km, easyKm: 0, race: true, date: eventDate, type: "Futás", title: `Verseny: ${event.label}`, duration: Math.round((paces?.predictions?.[eventType] || event.km * easyPace * 0.9) / 60 / 5) * 5,
      intensity: "magas", rpe: 9, purpose: `${event.label} · verseny`, note: paces ? `Célidő-becslés: ${formatDuration(paces.predictions[eventType])}. Kezdd egyenletesen, az első harmadban ne gyorsíts.` : "Kezdd egyenletesen, az első harmadban ne gyorsíts." });
  } else {
    // marathon-pace finish only every other specific week, so those weeks stay mostly easy (seiler2010)
    const marathonFinish = eventType === "marathon" && phase === "Versenyspecifikus" && level !== "kezdő" && weekNumber % 2 === 1;
    sessions.push({ km: weekLong, easyKm: marathonFinish ? weekLong * 0.8 : weekLong, date: dateOf(longDay), type: "Futás", title: `Hosszú futás · ${weekLong} km`, duration: minutes(weekLong, 1.03), intensity: marathonFinish ? "közepes" : "könnyű",
      rpe: marathonFinish ? 6 : 4, purpose: `${event.label} · ${phase.toLowerCase()}`,
      note: [marathonFinish ? `Az utolsó ${Math.round(weekLong * 0.2)} km maratoni tempóban (${paceText("marathon") || "versenytempó"}).` : `Egyenletes, könnyű tempó${paceText("easy") ? ` (${paceText("easy")})` : ""}.`, "Gyakorold a frissítést és a versenyfelszerelést."].join(" ") });
  }
  const freeDays = days.filter(code => !sessions.some(item => item.date === dateOf(code)));
  freeDays.slice(0, strengthCount).forEach(code => sessions.push({ date: dateOf(code), type: "Erő", title: "Futást támogató erőedzés", duration: 40, intensity: "közepes", rpe: 6,
    purpose: `${event.label} · ${phase.toLowerCase()}`, note: "Alsótest, csípő és törzs; kemény futás előtti napon kerüld a nehéz lábedzést." }));
  return sessions.map((item, index) => ({ ...item, id: `event-${eventType}-${item.date}-${index}`, status: "planned" }));
}
