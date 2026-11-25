import { budapestToday } from "./overviewData.js";

// null/"" must stay unknown: Number(null) is 0.
const known = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) && Number(value) >= 0;

// Equal-length period comparison of synced sessions; unknown values stay null, never zero.
export function summarizeTrainingPeriods(sessions, days, referenceDate) {
  const safeDays = Math.max(1, Number(days) || 7),
    reference = /^\d{4}-\d{2}-\d{2}$/.test(referenceDate || "") ? referenceDate : budapestToday(),
    shiftDate = (value, offset) => {
      const date = new Date(`${value}T12:00:00Z`);
      date.setUTCDate(date.getUTCDate() + offset);
      return date.toISOString().slice(0, 10);
    },
    currentFrom = shiftDate(reference, -safeDays + 1),
    previousTo = shiftDate(currentFrom, -1),
    previousFrom = shiftDate(previousTo, -safeDays + 1),
    validSessions = Array.isArray(sessions)
      ? sessions.filter((item) => /^\d{4}-\d{2}-\d{2}$/.test(item?.date || ""))
      : [],
    aggregate = (from, to) => {
      const items = validSessions.filter((item) => item.date >= from && item.date <= to),
        minutesKnown = items.every((item) => known(item.durationMin)),
        loadKnown = items.every((item) => known(item.load)),
        strengthCount = items.filter((item) => item.type === "Erő").length,
        officialLoads = items.filter((item) => item.loadSource === "garmin_activity_training_load").length;
      return {
        count: items.length,
        minutes: minutesKnown ? items.reduce((sum, item) => sum + Number(item.durationMin), 0) : null,
        load: loadKnown ? items.reduce((sum, item) => sum + Number(item.load), 0) : null,
        strengthRatio: items.length ? Math.round((strengthCount / items.length) * 100) : null,
        officialLoadCoverage: items.length ? Math.round((officialLoads / items.length) * 100) : null,
      };
    },
    formatRange = (from, to) => `${new Date(`${from}T12:00:00Z`).toLocaleDateString("hu-HU")} – ${new Date(`${to}T12:00:00Z`).toLocaleDateString("hu-HU")}`;
  return {
    days: safeDays,
    reference,
    current: aggregate(currentFrom, reference),
    previous: aggregate(previousFrom, previousTo),
    currentLabel: formatRange(currentFrom, reference),
    previousLabel: formatRange(previousFrom, previousTo),
  };
}

export function percentChange(current, previous) {
  return Number.isFinite(current) && Number.isFinite(previous) && previous > 0
    ? Math.round(((current - previous) / previous) * 100)
    : null;
}

export function formatMinutes(minutes) {
  if (!Number.isFinite(minutes)) return "nem ismert időtartam";
  const rounded = Math.round(minutes);
  return rounded >= 60 ? `${Math.floor(rounded / 60)} óra ${rounded % 60} perc` : `${rounded} perc`;
}

function signedPercent(value) {
  if (!Number.isFinite(value)) return "nem hasonlítható össze";
  return `${value > 0 ? "+" : ""}${value}%`;
}

export function buildTrainingInterpretation(comparison, profile, preferredAction = "") {
  const { current, previous, days } = comparison,
    minutesChange = percentChange(current.minutes, previous.minutes),
    loadChange = percentChange(current.load, previous.load),
    sessionChange = current.count - previous.count,
    enoughHistory = previous.count > 0,
    sourceCoverage = current.officialLoadCoverage;
  if (!current.count) {
    return {
      items: [
        ["Mi változott?", "Erre az időszakra nincs rögzített edzés, így változást sem tudunk számolni."],
        ["Mi állhat mögötte?", "Lehet, hogy pihentél, de az is, hogy hiányos a szinkron. A hiányzó adat nem nulla."],
        ["Mit tehetsz?", "Nézd meg az Áttekintésen, mikori az utolsó adat, és csak friss adatokból tervezz."],
      ],
      note: "Korlátozott értékelés: ebben az időszakban nincs elég edzésadat.",
    };
  }
  if (!enoughHistory) {
    return {
      items: [
        ["Mi változott?", `${current.count} edzést látunk, ${formatMinutes(current.minutes)}, de az előző ${days} napból nincs összehasonlítható edzés.`],
        ["Mi állhat mögötte?", "Kevés még az előzmény vagy a szinkronizált adat ahhoz, hogy megbízható irányt lássunk."],
        ["Mit tehetsz?", preferredAction || `Tartsd a ${profile.goal.toLowerCase()} célodhoz igazított tervet, és ne egyetlen időszakból ítélj.`],
      ],
      note: `Korlátozott összehasonlítás · edzések Garmin-terheléssel: ${sourceCoverage ?? "nem ismert"}%`,
    };
  }
  const changeText = `${current.count} edzés (${sessionChange > 0 ? "+" : ""}${sessionChange} alkalom), ${formatMinutes(current.minutes)} (${signedPercent(minutesChange)}), összterhelés: ${current.load?.toLocaleString("hu-HU") ?? "nem ismert"} pont (${signedPercent(loadChange)}).`,
    intensityShift = Number.isFinite(loadChange) && Number.isFinite(minutesChange) ? loadChange - minutesChange : null,
    causeText = intensityShift != null && intensityShift > 12
      ? "A terhelés gyorsabban nőtt, mint az edzésidő. Lehet, hogy intenzívebb vagy egyenként megterhelőbb edzéseid voltak, de ez önmagában nem bizonyít okot."
      : intensityShift != null && intensityShift < -12
        ? "Az edzésidőhöz képest kisebb lett a terhelés. Ez azzal is összefügghet, hogy több könnyű vagy regeneráló edzésed volt."
        : sessionChange !== 0
          ? `A változás főleg az edzések számán látszik: ${Math.abs(sessionChange)} alkalommal ${sessionChange > 0 ? "több" : "kevesebb"} edzést látunk.`
          : "Az edzések száma és a terhelés aránya nagyjából állandó. Nincs egyetlen kiugró jel, ami megmagyarázná.",
    actionText = preferredAction || (loadChange != null && loadChange > 20
      ? "A következő héten ne növeld egyszerre az időt és az intenzitást. Előbb figyeld meg, hogyan regenerálódsz."
      : loadChange != null && loadChange < -20
        ? "Ha ezt pihenőnek vagy könnyebb időszaknak szántad, tartsd a tervet. Ha nem, nézd meg, miért maradtak ki edzések."
        : `Tartsd a mostani ritmust, és a következő változtatást a ${profile.goal.toLowerCase()} célodhoz és a napi állapotodhoz igazítsd.`);
  return {
    items: [["Mi változott?", changeText], ["Mi állhat mögötte?", causeText], ["Mit tehetsz?", actionText]],
    note: `Két ugyanolyan hosszú időszakot hasonlítunk össze · edzések Garmin-terheléssel: ${sourceCoverage ?? "nem ismert"}% · a magyarázat kapcsolatot jelez, nem bizonyított okot.`,
  };
}

