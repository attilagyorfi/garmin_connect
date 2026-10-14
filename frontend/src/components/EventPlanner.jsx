import { useMemo, useState } from "react";
import { AlertTriangle, BookOpen, Flag, X } from "lucide-react";
import { MetricHelp } from "./Explainability.jsx";
import { isoDate } from "../lib/dates.js";
import { EVENTS, SOURCES, buildEventPlan, formatDuration, formatPace, inferEventType, parseRaceTime } from "../lib/eventTemplates.js";
import { isHikeEvent } from "../lib/hikeTemplates.js";
import { HikePlanner } from "./HikePlanner.jsx";

const shortDay = value => new Date(`${value}T12:00:00`).toLocaleDateString("hu-HU", { month: "short", day: "numeric" });
const weekday = value => new Date(`${value}T12:00:00`).toLocaleDateString("hu-HU", { weekday: "short", month: "short", day: "numeric" });

// Hiking events get their own planner; separate components keep each one's hooks stable when the event type changes.
export function EventPlanner(props) {
  return isHikeEvent(props.profile?.eventType) ? <HikePlanner {...props} /> : <RunningPlanner {...props} />;
}

// Event-specific running plan (5 km – marathon) from the profile's event, the athlete's recent Garmin running
// and an optional reference race. Saved sessions stay editable in the calendar like any other plan.
function RunningPlanner({ profile, data, plans, onSave, onEditProfile }) {
  const eventType = inferEventType(profile);
  const [open, setOpen] = useState(false), [replace, setReplace] = useState(true), [saved, setSaved] = useState(false);
  const referenceSeconds = parseRaceTime(profile.referenceRaceTime);
  const plan = useMemo(() => eventType ? buildEventPlan({ profile, data, eventType, referenceKey: profile.referenceRaceKey, referenceSeconds }) : null,
    [profile, data, eventType, referenceSeconds]);
  if (!plan) return <section className="card event-planner event-planner-empty"><div><span className="eyebrow">ESEMÉNYFELKÉSZÜLÉS</span><h2>Futóverseny vagy hegyi túra?</h2><p>Add meg a Profilban az esemény típusát és dátumát – maraton, félmaraton, 10 vagy 5 km, egynapos hegyi túra vagy többnapos túra –, és a Garmin-adataidból forrásolt, szakaszolt felkészülési tervet készítünk.</p></div><button className="primary" onClick={onEditProfile}>ESEMÉNY MEGADÁSA</button></section>;

  const { summary, weeks, paces, warnings } = plan;
  const sessions = weeks.flatMap(week => week.sessions);
  const span = weeks.flatMap(week => Array.from({ length: 7 }, (_, index) => { const date = new Date(`${week.weekStart}T12:00:00`); date.setDate(date.getDate() + index); return isoDate(date); }));
  const spanSet = new Set(span), conflicts = (plans || []).filter(item => spanSet.has(item.date));
  const save = () => { onSave({ plans: sessions, replacePlanDates: replace ? span : [] }); setSaved(true); setOpen(false); };
  const title = `${profile.eventName || EVENTS[eventType].label} · ${summary.weeks} hetes felkészülés`;

  return <section className="card event-planner">
    <div><span className="eyebrow">FUTÓVERSENY-FELKÉSZÜLÉS · {EVENTS[eventType].label.toUpperCase()}</span><h2>{title}</h2>
      <p>Alapozás, építés, versenyspecifikus szakasz és taper a mostani heti {summary.current.weeklyKm != null ? `${summary.current.weeklyKm.toLocaleString("hu-HU")} km-es futásodból` : "becsült kiindulásból"} indulva. A volumen hetente legfeljebb 10%-kal nő, minden negyedik hét könnyebb.</p>
      <div className="event-planner-stats">
        <span><b>{summary.peakKm.toLocaleString("hu-HU")} km</b><MetricHelp term="Csúcsvolumen" text="A terv legnagyobb heti futótávja. Nem cél önmagában: a terhelés fokozatosan, tehermentesítő hetekkel épül fel."><small>CSÚCSHÉT</small></MetricHelp></span>
        <span><b>{summary.longestRunKm.toLocaleString("hu-HU")} km</b><MetricHelp term="Leghosszabb futás" text="A leghosszabb tervezett futás. Maratonra edzői gyakorlat szerint kb. 30–32 km a felső határ; hosszabb futás több regenerációt kér, mint amennyit hoz."><small>LEGHOSSZABB FUTÁS</small></MetricHelp></span>
        <span><b>{summary.taperWeeks} hét</b><MetricHelp term="Taper" text="A verseny előtti visszaterhelés: a heti volumen fokozatosan 41–60%-kal csökken, az intenzitás és az edzésgyakoriság marad (Bosquet és mtsai, 2007; Wang és mtsai, 2023)."><small>TAPER</small></MetricHelp></span>
        <span><b>{summary.predictedSeconds ? formatDuration(summary.predictedSeconds) : "—"}</b><MetricHelp term="Becsült célidő" text="Riegel-formulával a megadott referenciaeredményből. Sík pályára és megfelelő felkészülésre érvényes; melegben, emelkedős pályán lassabb lesz."><small>BECSÜLT IDŐ</small></MetricHelp></span>
      </div>
    </div>
    {!summary.distanceReady && <p className="event-planner-alert" role="note"><AlertTriangle size={16} aria-hidden="true" /><span>{warnings[0]}</span></p>}
    <div className="event-planner-actions"><button className="primary" onClick={() => setOpen(true)}>TERV ELŐNÉZETE</button>{saved && <span className="periodization-saved">A felkészülési terv bekerült a Naptárba.</span>}</div>
    {open && <div className="modal-backdrop" onClick={() => setOpen(false)}><div className="modal event-plan-modal" role="dialog" aria-modal="true" aria-label="Futóverseny-felkészülési terv" onClick={event => event.stopPropagation()}>
      <button className="close" aria-label="Ablak bezárása" onClick={() => setOpen(false)}><X size={18} /></button>
      <span className="eyebrow"><Flag size={13} aria-hidden="true" /> {EVENTS[eventType].label.toUpperCase()} · {plan.event.date ? shortDay(plan.event.date) : "dátum nélkül"} · {plan.event.level}</span>
      <h2>{title}</h2>
      {warnings.length > 0 && <div className="event-plan-warnings" role="note">{warnings.map(text => <p key={text}><AlertTriangle size={15} aria-hidden="true" /><span>{text}</span></p>)}</div>}
      {paces && <div className="event-plan-paces"><h3>Tempózónák</h3><p>A {EVENTS[profile.referenceRaceKey].label.toLowerCase()} {formatDuration(referenceSeconds)}-es eredményedből becsülve. Pulzus és közérzet felülírhatja: rossz napon a könnyű futás legyen tényleg könnyű.</p><div>{paces.zones.map(zone => <span key={zone.key}><b>{zone.label}</b><strong>{zone.from === zone.to ? formatPace(zone.from) : `${formatPace(zone.from)} – ${formatPace(zone.to)}`}</strong><small>{zone.note}</small></span>)}</div></div>}
      <div className="periodization-weeks event-plan-weeks">{weeks.map(week => <details key={week.index} open={week.index === 1 || week.index === weeks.length}>
        <summary><span><b>{week.index}. hét · {week.phase}</b><small>{shortDay(week.weekStart)} · {week.sessions.filter(item => item.type === "Futás").length} futás · hosszú: {week.longKm.toLocaleString("hu-HU")} km{week.easyShare != null ? ` · ${week.easyShare}% könnyű` : ""}</small></span><strong>{week.trainingKm.toLocaleString("hu-HU")}<small> km{week.raceKm ? " + verseny" : ""}</small></strong></summary>
        <div className="periodization-week-detail">{[...week.sessions].sort((a, b) => a.date.localeCompare(b.date)).map(item => <div key={item.id}><time>{weekday(item.date)}</time><span>{item.title}<small className="event-plan-note">{item.note}</small></span><small>{item.duration}p · RPE {item.rpe}</small></div>)}</div>
      </details>)}</div>
      <details className="event-plan-sources"><summary><BookOpen size={15} aria-hidden="true" /> Mire épül a terv?</summary>
        <p>A taper, az intenzitáseloszlás és az időbecslés tudományos forrásokra épül. A csúcsvolumen, a hosszú futás felső határa és a négyhetes tehermentesítési ritmus bevett edzői gyakorlat, nem szigorú bizonyíték; a heti 10%-os emelés óvatos választás, mert biztonságos arányt egyik vizsgálat sem igazolt.</p>
        <ul>{SOURCES.map(source => <li key={source.key}><b>{source.claim}</b><a href={source.url} target="_blank" rel="noreferrer">{source.label}</a></li>)}</ul>
        <p className="event-plan-disclaimer">Sportteljesítményi támogatás, nem orvosi tanács. Fájdalom, betegség vagy szokatlan fáradtság esetén pihenj, és szükség esetén fordulj sportorvoshoz.</p>
      </details>
      {conflicts.length > 0 && <label className="periodization-conflict"><input type="checkbox" checked={replace} onChange={event => setReplace(event.target.checked)} /><span>A terv időszakában lévő {conflicts.length} meglévő edzést lecserélem</span></label>}
      <div className="template-editor-actions"><button onClick={() => setOpen(false)}>Mégse</button><button className="primary" disabled={conflicts.length > 0 && !replace} onClick={save}>Felkészülési terv mentése a Naptárba</button></div>
    </div></div>}
  </section>;
}
