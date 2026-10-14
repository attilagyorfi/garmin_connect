// Hiking event plans: a one-day mountain hike or a multi-day trek with a backpack. Pure functions: no network, no storage.
// Evidence where it exists (combined training and progressive load carriage, downhill preconditioning, altitude, taper);
// time estimates follow the DIN 33466 walking-time convention; the rest (progression, cut-back rhythm, peak long hike
// relative to the event) is conventional coaching practice and is labelled as such.

import { isoDate } from "./dates.js";

export const HIKE_SOURCES = [
  { key: "knapik2012", label: "Knapik JJ, Harman EA, Steelman RA, Graham BS. A systematic review of the effects of physical training on load carriage performance. J Strength Cond Res. 2012;26(2):585–597.", url: "https://doi.org/10.1519/JSC.0b013e3182429853", claim: "Nagy javulás, ha az erőedzést állóképességi edzéssel kombinálják, heti legalább 3 alkalommal, legalább 4 héten át; fokozatosan növelt hátizsákos edzéssel a hatás még nagyobb." },
  { key: "bontemps2020", label: "Bontemps B, Vercruyssen F, Gruet M, Louis J. Downhill running: what are the effects and how can we adapt? A narrative review. Sports Med. 2020;50(12):2083–2110.", url: "https://doi.org/10.1007/s40279-020-01355-z", claim: "A lejtmenet izomkárosodása ellen az előzetes lejtős terhelés a legjobban alátámasztott védekezés; a védőhatás hetekig tart (6 hétnél még igen, 9 hétnél már nem volt kimutatható)." },
  { key: "din33466", label: "DIN 33466 – Wanderwege (gyalogidő-számítás), Österreichischer Alpenverein ismertetője.", url: "https://www.alpenverein.at/portal/news/aktuelle_news_kurz/2018/2018_06_14_wie-berechnet-man-die-gehzeit-auf-wanderwegen.php", claim: "Óránként kb. 300 m emelkedés, 500 m lejtés vagy 4 km vízszintes táv; a kisebbik időt felezve adjuk a nagyobbikhoz. Irányérték, pihenők nélkül." },
  { key: "luks2019", label: "Luks AM, Auerbach PS, Freer L, et al. Wilderness Medical Society clinical practice guidelines for the prevention and treatment of acute altitude illness: 2019 update. Wilderness Environ Med. 2019;30(4S):S3–S18.", url: "https://doi.org/10.1016/j.wem.2019.04.006", claim: "2500 m felett nő a magassági betegség kockázata; 3000 m felett az alvási magasság naponta legfeljebb kb. 500 m-rel nőjön, 3–4 naponta pihenőnappal." },
  { key: "bosquet2007", label: "Bosquet L, Montpetit J, Arvisais D, Mujika I. Effects of tapering on performance: a meta-analysis. Med Sci Sports Exerc. 2007;39(8):1358–1365.", url: "https://doi.org/10.1249/mss.0b013e31806010e0", claim: "Állóképességi sportokban a volumen 41–60%-os csökkentése az intenzitás megtartásával segíti a csúcsformát; túrázásra átvett, nem külön vizsgált elv." },
];

const EXPERIENCE_KEYS = ["kezdő", "középhaladó", "haladó"];

// Coaching practice: the long training hike builds to about 75% of the event day (one-day hike), or to back-to-back days
// whose first day reaches about 75% of a trek day; a typical starting long hike per experience level when there is no Garmin hiking data.
export const HIKE_EVENTS = {
  hike: { label: "Egynapos hegyi túra", weeks: { min: 6, rec: 10, max: 16 }, taper: [0.6], peakShare: 0.75, defaultPack: 5, phrase: "az egynapos túra" },
  trek: { label: "Többnapos túra", weeks: { min: 8, rec: 12, max: 20 }, taper: [0.7, 0.5], peakShare: 0.75, defaultPack: 12, phrase: "a többnapos túra" },
};
export const HIKE_KEYS = Object.keys(HIKE_EVENTS);
const START_MINUTES = { kezdő: 120, középhaladó: 150, haladó: 180 };
const MAX_WEEKLY_INCREASE = 0.1; // conservative, as for the running plans
const CUTBACK_EVERY = 4;
const CUTBACK_FACTOR = 0.8;
const MAX_PACK_STEP_KG = 2;
const ORDER = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];

const round5 = value => Math.round(value / 5) * 5;
const round50 = value => Math.round(value / 50) * 50;
const roundHalf = value => Math.round(value * 2) / 2;
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

export const isHikeEvent = key => Boolean(HIKE_EVENTS[key]);

/** DIN 33466 walking time in minutes (ascent 300 m/h, descent 500 m/h, 4 km/h; the smaller part counts half). */
export function walkingMinutes(km, gainM, lossM = gainM) {
  const horizontal = Math.max(0, km) / 4, vertical = Math.max(0, gainM) / 300 + Math.max(0, lossM) / 500;
  return (Math.max(horizontal, vertical) + Math.min(horizontal, vertical) / 2) * 60;
}

export function formatHours(minutes) {
  const total = Math.round(minutes / 5) * 5;
  return `${Math.floor(total / 60)} ó ${String(total % 60).padStart(2, "0")} p`;
}

/** The event as entered in the profile; missing or out-of-range numbers fall back to null (the UI asks for them). */
export function hikeTarget(profile) {
  const number = (value, low, high) => { const parsed = Number(value); return Number.isFinite(parsed) && parsed >= low && parsed <= high ? parsed : null; };
  const type = HIKE_EVENTS[profile?.eventType] ? profile.eventType : null;
  if (!type) return null;
  return {
    type, km: number(profile.hikeKm, 3, 80), gainM: number(profile.hikeGainM, 100, 3500),
    days: type === "trek" ? number(profile.hikeDays, 2, 21) ?? 3 : 1,
    packKg: number(profile.hikePackKg, 0, 25) ?? HIKE_EVENTS[type].defaultPack,
    maxAltitudeM: number(profile.hikeMaxAltitudeM, 0, 6000),
  };
}

/**
 * Recent hiking from synced sessions (last 8 weeks): the longest hike, the most climbing in one hike, and a personal
 * pace factor (actual time / DIN estimate) when at least two hikes have distance and ascent. Missing data stays null.
 */
export function currentHiking(sessions, today) {
  const end = new Date(`${today}T12:00:00`), start = new Date(end);
  start.setDate(end.getDate() - 55);
  const from = isoDate(start);
  const hikes = (sessions || []).filter(item => item?.type === "Túrázás" && item.date >= from && item.date <= today && Number(item.durationMin) > 0);
  if (!hikes.length) return { hikes: 0, longestMin: null, maxGainM: null, paceFactor: null };
  const measured = hikes.filter(item => Number(item.distanceKm) > 2 && Number(item.ascentM) > 50)
    .map(item => Number(item.durationMin) / walkingMinutes(Number(item.distanceKm), Number(item.ascentM))).sort((a, b) => a - b);
  const gains = hikes.map(item => Number(item.ascentM)).filter(value => Number.isFinite(value) && value > 0);
  return {
    hikes: hikes.length, longestMin: Math.max(...hikes.map(item => Number(item.durationMin))),
    maxGainM: gains.length ? Math.max(...gains) : null,
    // median, clamped: Garmin time includes short stops, and a single odd hike must not skew the plan
    paceFactor: measured.length >= 2 ? clamp(measured[Math.floor(measured.length / 2)], 0.7, 1.4) : null,
  };
}

function mondayOnOrAfter(iso) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + ((8 - date.getDay()) % 7));
  return date;
}

function weeksBetween(fromIso, toIso) {
  return Math.floor((new Date(`${toIso}T12:00:00`) - new Date(`${fromIso}T12:00:00`)) / (7 * 86400000));
}

/**
 * Build the plan. Returns { event, weeks, summary, warnings } or null when the event is not a hike or lacks distance/gain.
 * The long hike grows at most 10% per week in time, with every 4th week easier; climbing and pack weight follow it.
 */
export function buildHikePlan({ profile, data, today }) {
  const target = hikeTarget(profile);
  if (!target || target.km == null || target.gainM == null) return null;
  const event = HIKE_EVENTS[target.type];
  const level = EXPERIENCE_KEYS.includes(profile?.experience) ? profile.experience : "középhaladó";
  const warnings = [];
  const todayIso = today || data?.today || isoDate(new Date());
  const firstMonday = mondayOnOrAfter(todayIso);
  const eventDate = profile?.eventDate && profile.eventDate > todayIso ? profile.eventDate : null;

  let weekCount = event.weeks.rec, start = new Date(firstMonday);
  if (eventDate) {
    const available = weeksBetween(isoDate(firstMonday), eventDate) + 1;
    if (available < event.weeks.min) warnings.push(`Az eseményig ${available} hét van, ${event.phrase} szokásos minimális felkészülési ideje ${event.weeks.min} hét. A terv rövidített; a túra napján tervezz több pihenőt és tartalékidőt.`);
    weekCount = Math.max(2, Math.min(event.weeks.max, available));
    start = new Date(`${eventDate}T12:00:00`);
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7) - (weekCount - 1) * 7);
    if (available > event.weeks.max) warnings.push(`Az eseményig ${available} hét van; a ${weekCount} hetes célzott terv ${start.toLocaleDateString("hu-HU", { month: "long", day: "numeric" })}-én indul, addig tartsd a mostani túrázási és edzési szokásaidat.`);
  } else {
    warnings.push(`Nincs megadva eseménydátum, ezért a javasolt ${weekCount} hetes tervet a következő hétfőtől számoljuk.`);
  }

  const current = currentHiking(data?.sessions, todayIso);
  const paceFactor = current.paceFactor ?? 1;
  const dayMinutes = walkingMinutes(target.km, target.gainM) * paceFactor;
  const climbRate = target.gainM / dayMinutes, kmRate = target.km / dayMinutes; // the event's own mix of distance and climbing
  if (current.longestMin == null) warnings.push("Az elmúlt 8 hétből nincs Garmin-túraadat, ezért a kiinduló túrahossz a tapasztalati szinted alapján becsült.");
  if (current.paceFactor == null) warnings.push("A menetidő a DIN 33466 szerinti átlagos tempóval becsült; néhány szintemelkedéssel rögzített Garmin-túra után a saját tempódhoz igazítjuk.");

  const peakMinutes = dayMinutes * event.peakShare;
  const startMinutes = Math.min(peakMinutes, current.longestMin != null ? Math.max(60, current.longestMin) : START_MINUTES[level]);
  const taperWeeks = Math.min(event.taper.length, Math.max(1, weekCount - 1));
  const buildWeeks = weekCount - taperWeeks;
  const longs = [];
  let base = startMinutes;
  for (let index = 0; index < buildWeeks; index += 1) {
    const cutback = (index + 1) % CUTBACK_EVERY === 0 && index < buildWeeks - 1;
    // after a cut-back week the load only returns to the previous level; it grows again a week later
    if (index > 0 && !cutback && !longs[index - 1].cutback) base = Math.min(peakMinutes, base * (1 + MAX_WEEKLY_INCREASE));
    longs.push({ minutes: cutback ? base * CUTBACK_FACTOR : base, cutback });
  }
  const peakReached = Math.max(...longs.map(item => item.minutes));
  event.taper.slice(event.taper.length - taperWeeks).forEach(factor => longs.push({ minutes: peakReached * factor, taper: true }));

  const startPack = Math.min(target.packKg, 5);
  const days = (profile?.trainingDays || ["H", "K", "Sze", "Cs", "P", "Szo"]).filter(day => day !== profile?.restDay);
  const sorted = [...days].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
  const longDay = sorted.includes("Szo") ? "Szo" : sorted.includes("V") ? "V" : sorted[sorted.length - 1];
  const backDay = target.type === "trek" && longDay === "Szo" && sorted.includes("V") ? "V" : null;
  if (target.type === "trek" && !backDay) warnings.push("Többnapos túrához a hétvégi, egymást követő túranapok (szombat–vasárnap) a leghasznosabbak; add meg mindkettőt edzésnapként, ha teheted.");

  let pack = startPack;
  const weeks = longs.map((long, index) => {
    const weekStart = new Date(start);
    weekStart.setDate(start.getDate() + index * 7);
    const share = (index + 1) / buildWeeks;
    const phase = long.taper ? "Taper" : long.cutback ? "Tehermentesítés" : share <= 0.4 ? "Alapozás" : share <= 0.8 ? "Építés" : "Eseményspecifikus";
    // like the hike length: after a cut-back week the pack only returns to its previous weight
    if (!long.taper && !long.cutback && index > 0 && !longs[index - 1].cutback) pack = Math.min(target.packKg, pack + MAX_PACK_STEP_KG);
    const weekPack = long.taper ? Math.min(pack, target.packKg) : long.cutback ? Math.max(startPack, pack - MAX_PACK_STEP_KG) : pack;
    const minutes = round5(long.minutes);
    const sessions = buildHikeWeek({ index, weekStart, phase, early: share <= 0.4, long, minutes, pack: weekPack, climbRate, kmRate, target, event, days: sorted, longDay, backDay, eventDate, dayMinutes, profile });
    const hikeMinutes = sessions.filter(item => item.type === "Túrázás" && !item.event).reduce((sum, item) => sum + item.duration, 0);
    const eventWeek = sessions.some(item => item.event);
    return { index: index + 1, phase, weekStart: isoDate(weekStart), eventWeek, longMinutes: eventWeek ? 0 : minutes, longGainM: eventWeek ? 0 : round50(minutes * climbRate), packKg: weekPack, hikeMinutes,
      sessions: sessions.map(({ event: _event, ...plan }) => plan) };
  });

  const longestPlanned = Math.max(...weeks.map(week => week.longMinutes));
  const ready = longestPlanned >= dayMinutes * event.peakShare * 0.85;
  if (!ready) warnings.unshift(`A mostani túrázásodból a heti legfeljebb 10%-os emeléssel a leghosszabb edzéstúra ${formatHours(longestPlanned)}-ig jut, ami kevés a ${formatHours(dayMinutes)}-s túranaphoz (kb. ${formatHours(dayMinutes * event.peakShare)} lenne a cél). Válassz rövidebb útvonalat, vagy egy későbbi időpontot.`);
  if (dayMinutes > 12 * 60) warnings.push(`A becsült menetidő ${formatHours(dayMinutes)} egy napra: ilyen hosszú túrához tervezz sötétben megtett szakasszal, frissítőpontokkal, és jelölj ki menekülőutat.`);
  if (target.maxAltitudeM != null && target.maxAltitudeM >= 2500) {
    warnings.push(target.type === "trek" && target.maxAltitudeM >= 3000
      ? "A túra 3000 m fölé visz: ott az alvási magasság naponta legfeljebb kb. 500 m-rel nőjön, és 3–4 naponta legyen pihenőnap (Luks és mtsai, 2019). Magashegyi úthoz kérj sportorvosi tanácsot."
      : "A túra 2500 m fölé visz, ahol nő a magassági betegség kockázata (Luks és mtsai, 2019). Ha teheted, aludj előtte egy éjszakát közepes magasságban, és fejfájásnál, hányingernél ne menj tovább felfelé.");
  }
  return {
    event: { key: target.type, label: event.label, date: eventDate, level, ...target },
    weeks, warnings,
    summary: { weeks: weeks.length, ready, dayMinutes, paceFactor: current.paceFactor, longestMinutes: longestPlanned, peakGainM: Math.max(...weeks.map(week => week.longGainM)),
      packKg: target.packKg, taperWeeks, current },
  };
}

function buildHikeWeek({ index, weekStart, phase, early, long, minutes, pack, climbRate, kmRate, target, event, days, longDay, backDay, eventDate, dayMinutes, profile }) {
  const dateOf = code => { const date = new Date(weekStart); date.setDate(weekStart.getDate() + ORDER.indexOf(code)); return isoDate(date); };
  const purpose = `${event.label} · ${phase.toLowerCase()}`;
  const sessions = [];
  const eventDays = eventDate ? Array.from({ length: target.days }, (_, offset) => { const date = new Date(`${eventDate}T12:00:00`); date.setDate(date.getDate() + offset); return isoDate(date); }) : [];
  const inWeek = iso => dateOf("H") <= iso && iso <= dateOf("V");
  const eventWeek = eventDays.some(inWeek);

  if (eventWeek) {
    // a trek may run past Sunday: every event day belongs to the event week
    eventDays.forEach((iso, offset) => sessions.push({ event: true, date: iso, type: "Túrázás", title: `${target.days > 1 ? `${offset + 1}. túranap` : "Túra"}: ${profile?.eventName || event.label}`,
      duration: Math.min(1440, round5(dayMinutes)), intensity: "közepes", rpe: 6, purpose: `${event.label} · esemény`,
      note: `Kb. ${target.km} km és ${target.gainM} m szint${target.packKg ? `, ${target.packKg} kg hátizsák` : ""}. Becsült menetidő pihenők nélkül: ${formatHours(dayMinutes)}. Indulj egyenletes, beszélgetős tempóban, óránként igyál és egyél.` }));
  } else {
    // The long hike: climbing follows the event's own mix; every other build week the descent is the focus (bontemps2020).
    const descentFocus = (phase === "Építés" || phase === "Eseményspecifikus") && index % 2 === 1;
    const lastDescent = phase === "Taper";
    sessions.push({ date: dateOf(longDay), type: "Túrázás", title: `Hosszú edzéstúra · ${formatHours(minutes)}`, duration: minutes, intensity: long.taper || long.cutback ? "könnyű" : "könnyű–közepes", rpe: long.taper || long.cutback ? 3 : 5, purpose,
      note: [`Kb. ${roundHalf(minutes * kmRate)} km és ${round50(minutes * climbRate)} m szint${pack ? `, ${pack} kg hátizsákkal` : ""}.`,
        descentFocus ? "Ma a lejtő a lényeg: ereszkedj tudatosan, rövid lépésekkel – ez edzi a combot a hosszú lejtmenetekre." : lastDescent ? "Könnyű, rövidebb túra; hosszú, meredek lejtmenetet ezen a héten már kerülj." : "Egyenletes, beszélgetős tempó; próbáld ki a túrafelszerelést és a frissítést."].join(" ") });
    if (backDay && !long.taper && !early) {
      const second = round5(minutes * 0.7);
      sessions.push({ date: dateOf(backDay), type: "Túrázás", title: `Második túranap · ${formatHours(second)}`, duration: second, intensity: "könnyű", rpe: 4, purpose,
        note: `Fáradt lábbal, ugyanazzal a hátizsákkal (${pack} kg): ez készít fel az egymást követő túranapokra. Kb. ${round50(second * climbRate)} m szint.` });
    }
  }

  // Combined strength + aerobic work at least three times a week (knapik2012); most aerobic work stays easy.
  const free = days.filter(code => code !== longDay && code !== backDay && !sessions.some(item => item.date === dateOf(code)));
  const taper = long.taper || eventWeek;
  const strengthCount = taper ? 1 : 2;
  const strengthDays = free.filter((_, position) => position % 2 === 0).slice(0, strengthCount);
  strengthDays.forEach(code => sessions.push({ date: dateOf(code), type: "Erő", title: "Túrázást támogató erőedzés", duration: taper ? 30 : 45, intensity: taper ? "könnyű–közepes" : "közepes", rpe: taper ? 4 : 6, purpose,
    note: taper ? "Rövid, könnyű átmozgató erősítés; izomlázat okozó, nehéz lábedzést ne végezz." : "Fellépés (step-up) hátizsákkal, kitörés, egylábas guggolás, vádliemelés, lassú lelépés padról (lejtmenet-felkészítés), törzs. 3×8–12 ismétlés." }));
  const aerobicDays = free.filter(code => !strengthDays.includes(code)).slice(0, taper ? 1 : 2);
  aerobicDays.forEach((code, position) => {
    const climbing = !taper && position === 0 && (phase === "Építés" || phase === "Eseményspecifikus");
    sessions.push({ date: dateOf(code), type: "Kardió", title: climbing ? "Emelkedős intervall" : "Könnyű állóképességi edzés", duration: climbing ? 45 : taper ? 30 : 45,
      intensity: climbing ? "közepes–magas" : "könnyű", rpe: climbing ? 7 : 3, purpose,
      note: climbing ? "Bemelegítés után 6–8×3 perc tempós emelkedőmenet (lépcső, futópad emelkedővel vagy domb), lefelé lassú visszasétálás." : "Futás, kerékpár vagy lépcsőzés beszélgetős tempóban (Zone 2)." });
  });
  return sessions.map((item, position) => ({ ...item, id: `event-${target.type}-${item.date}-${position}`, status: "planned" }));
}
