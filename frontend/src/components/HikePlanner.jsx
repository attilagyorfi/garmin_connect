import { useMemo, useState } from "react";
import { AlertTriangle, BookOpen, Mountain, X } from "lucide-react";
import { MetricHelp } from "./Explainability.jsx";
import { isoDate } from "../lib/dates.js";
import { HIKE_EVENTS, HIKE_SOURCES, buildHikePlan, formatHours, hikeTarget } from "../lib/hikeTemplates.js";

const shortDay = value => new Date(`${value}T12:00:00`).toLocaleDateString("hu-HU", { month: "short", day: "numeric" });
const weekday = value => new Date(`${value}T12:00:00`).toLocaleDateString("hu-HU", { weekday: "short", month: "short", day: "numeric" });

// Hiking event plan (one-day mountain hike or multi-day trek) from the profile's route, recent Garmin hikes and the
// training days. Saved sessions stay editable in the calendar like any other plan.
export function HikePlanner({ profile, data, plans, onSave, onEditProfile }) {
  const [open, setOpen] = useState(false), [replace, setReplace] = useState(true), [saved, setSaved] = useState(false);
  const target = hikeTarget(profile);
  const plan = useMemo(() => buildHikePlan({ profile, data }), [profile, data]);
  const event = HIKE_EVENTS[target.type];
  if (!plan) return <section className="card event-planner event-planner-empty"><div><span className="eyebrow">TÚRAFELKÉSZÜLÉS · {event.label.toUpperCase()}</span><h2>Milyen hosszú és mennyi szint lesz?</h2><p>Add meg a Profilban a túra napi távját és szintemelkedését (többnapos túránál a napok számát és a hátizsák súlyát is), és a Garmin-túráidból fokozatos, forrásolt felkészülési tervet készítünk.</p></div><button className="primary" onClick={onEditProfile}>TÚRA ADATAINAK MEGADÁSA</button></section>;

  const { summary, weeks, warnings } = plan;
  const sessions = weeks.flatMap(week => week.sessions);
  const span = [...new Set([...weeks.flatMap(week => Array.from({ length: 7 }, (_, index) => { const date = new Date(`${week.weekStart}T12:00:00`); date.setDate(date.getDate() + index); return isoDate(date); })), ...sessions.map(item => item.date)])];
  const spanSet = new Set(span), conflicts = (plans || []).filter(item => spanSet.has(item.date));
  const save = () => { onSave({ plans: sessions, replacePlanDates: replace ? span : [] }); setSaved(true); setOpen(false); };
  const title = `${profile.eventName || event.label} · ${summary.weeks} hetes felkészülés`;
  const route = `${target.km.toLocaleString("hu-HU")} km, ${target.gainM.toLocaleString("hu-HU")} m szint${target.days > 1 ? ` naponta, ${target.days} nap` : ""}${target.packKg ? `, ${target.packKg} kg hátizsák` : ""}`;

  return <section className="card event-planner">
    <div><span className="eyebrow">TÚRAFELKÉSZÜLÉS · {event.label.toUpperCase()}</span><h2>{title}</h2>
      <p>{route}. A hosszú edzéstúra hetente legfeljebb 10%-kal hosszabbodik, a szint és a hátizsák súlya ezzel együtt nő, minden negyedik hét könnyebb; mellette heti két erőedzés és könnyű állóképességi munka.</p>
      <div className="event-planner-stats">
        <span><b>{formatHours(summary.dayMinutes)}</b><MetricHelp term="Becsült menetidő" text={`A DIN 33466 szerinti gyalogidő (óránként 300 m fel, 500 m le vagy 4 km vízszintes)${summary.paceFactor ? `, a saját Garmin-túráid tempójához igazítva (×${summary.paceFactor.toLocaleString("hu-HU", { maximumFractionDigits: 2 })})` : ""}. Pihenők nélkül értendő.`}><small>{target.days > 1 ? "EGY TÚRANAP" : "TÚRANAP"}</small></MetricHelp></span>
        <span><b>{formatHours(summary.longestMinutes)}</b><MetricHelp term="Leghosszabb edzéstúra" text={`Edzői gyakorlat szerint a felkészülés csúcsán a hosszú túra a túranap kb. ${Math.round(event.peakShare * 100)}%-áig ér${target.days > 1 ? ", hétvégén két egymást követő nappal" : ""}; a teljes távot a túra napjára tartogatjuk.`}><small>LEGHOSSZABB TÚRA</small></MetricHelp></span>
        <span><b>{summary.peakGainM.toLocaleString("hu-HU")} m</b><MetricHelp term="Csúcs szintemelkedés" text="A leghosszabb edzéstúra becsült szintemelkedése: a túra saját táv–szint arányát követi, hogy a lábad arra készüljön, ami vár rá."><small>CSÚCS SZINT</small></MetricHelp></span>
        <span><b>{summary.taperWeeks} hét</b><MetricHelp term="Visszaterhelés" text="A túra előtt a terhelés 40–60%-kal csökken, a rövid emelkedős munka marad. Az állóképességi sportokban igazolt elv (Bosquet és mtsai, 2007), túrázásra átvéve."><small>VISSZATERHELÉS</small></MetricHelp></span>
      </div>
    </div>
    {!summary.ready && <p className="event-planner-alert" role="note"><AlertTriangle size={16} aria-hidden="true" /><span>{warnings[0]}</span></p>}
    <div className="event-planner-actions"><button className="primary" onClick={() => setOpen(true)}>TERV ELŐNÉZETE</button>{saved && <span className="periodization-saved">A felkészülési terv bekerült a Naptárba.</span>}</div>
    {open && <div className="modal-backdrop" onClick={() => setOpen(false)}><div className="modal event-plan-modal" role="dialog" aria-modal="true" aria-label="Túrafelkészülési terv" onClick={clickEvent => clickEvent.stopPropagation()}>
      <button className="close" aria-label="Ablak bezárása" onClick={() => setOpen(false)}><X size={18} /></button>
      <span className="eyebrow"><Mountain size={13} aria-hidden="true" /> {event.label.toUpperCase()} · {plan.event.date ? shortDay(plan.event.date) : "dátum nélkül"} · {plan.event.level}</span>
      <h2>{title}</h2>
      {warnings.length > 0 && <div className="event-plan-warnings" role="note">{warnings.map(text => <p key={text}><AlertTriangle size={15} aria-hidden="true" /><span>{text}</span></p>)}</div>}
      <div className="periodization-weeks event-plan-weeks">{weeks.map(week => <details key={week.index} open={week.index === 1 || week.index === weeks.length}>
        <summary><span><b>{week.index}. hét · {week.phase}</b><small>{shortDay(week.weekStart)} · {week.eventWeek ? "a túra hete" : `hosszú túra: ${formatHours(week.longMinutes)}, kb. ${week.longGainM.toLocaleString("hu-HU")} m szint`}{week.packKg ? ` · ${week.packKg} kg` : ""}</small></span><strong>{formatHours(week.hikeMinutes)}<small> túra</small></strong></summary>
        <div className="periodization-week-detail">{[...week.sessions].sort((a, b) => a.date.localeCompare(b.date)).map(item => <div key={item.id}><time>{weekday(item.date)}</time><span>{item.title}<small className="event-plan-note">{item.note}</small></span><small>{item.duration}p · RPE {item.rpe}</small></div>)}</div>
      </details>)}</div>
      <details className="event-plan-sources"><summary><BookOpen size={15} aria-hidden="true" /> Mire épül a terv?</summary>
        <p>A kombinált erő- és állóképességi edzés, a fokozatos hátizsákos terhelés, a lejtmenetre felkészítés és a magassági óvatosság tudományos forrásokra épül; a menetidő a DIN 33466 szerinti szokásos becslés. A heti 10%-os emelés, a négyhetes tehermentesítés és a leghosszabb edzéstúra aránya bevett edzői gyakorlat, nem szigorú bizonyíték.</p>
        <ul>{HIKE_SOURCES.map(source => <li key={source.key}><b>{source.claim}</b><a href={source.url} target="_blank" rel="noreferrer">{source.label}</a></li>)}</ul>
        <p className="event-plan-disclaimer">Sportteljesítményi támogatás, nem orvosi tanács. Indulás előtt nézd meg az időjárást és az útvonal állapotát; fájdalom, betegség vagy szokatlan fáradtság esetén pihenj, és szükség esetén fordulj sportorvoshoz.</p>
      </details>
      {conflicts.length > 0 && <label className="periodization-conflict"><input type="checkbox" checked={replace} onChange={changeEvent => setReplace(changeEvent.target.checked)} /><span>A terv időszakában lévő {conflicts.length} meglévő edzést lecserélem</span></label>}
      <div className="template-editor-actions"><button onClick={() => setOpen(false)}>Mégse</button><button className="primary" disabled={conflicts.length > 0 && !replace} onClick={save}>Felkészülési terv mentése a Naptárba</button></div>
    </div></div>}
  </section>;
}
