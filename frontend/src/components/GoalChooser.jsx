import { Flag, Mountain } from "lucide-react";

// Evidence-based event templates first (each has a sourced preparation plan on the Goal page); general goals only
// for athletes without a concrete event. Picking an event sets the matching general goal, which the daily
// recommendations and weekly templates use for their cardio/strength weighting.
export const EVENT_CHOICES = [
  { key: "marathon", label: "Maraton", detail: "42,2 km", kind: "run" },
  { key: "half", label: "Félmaraton", detail: "21,1 km", kind: "run" },
  { key: "10k", label: "10 km", detail: "futóverseny", kind: "run" },
  { key: "5k", label: "5 km", detail: "futóverseny", kind: "run" },
  { key: "hike", label: "Egynapos hegyi túra", detail: "teljesítménytúra", kind: "hike" },
  { key: "trek", label: "Többnapos túra", detail: "hátizsákkal", kind: "hike" },
];
export const GENERAL_GOALS = [
  ["Hibrid teljesítmény", "Állóképesség és erő egyszerre"],
  ["Futóteljesítmény", "Gyorsabb futás, verseny nélkül"],
  ["Erőfejlesztés", "Több erő, kevesebb kardió"],
  ["Hegyi állóképesség", "Túrák, emelkedők, hátizsák"],
  ["Általános egészség", "Rendszeres mozgás, jó közérzet"],
];
const RACES = [["5k", "5 km"], ["10k", "10 km"], ["half", "Félmaraton"], ["marathon", "Maraton"]];
const HIKE_INPUTS = [
  { key: "hikeKm", label: "Táv (km)", min: 3, max: 80, step: 0.5, placeholder: "pl. 24" },
  { key: "hikeGainM", label: "Szintemelkedés (m)", min: 100, max: 3500, step: 50, placeholder: "pl. 1200" },
  { key: "hikeDays", label: "Napok száma", min: 2, max: 21, step: 1, placeholder: "pl. 4", trekOnly: true },
  { key: "hikePackKg", label: "Hátizsák (kg)", min: 0, max: 25, step: 0.5, placeholder: "pl. 8" },
  { key: "hikeMaxAltitudeM", label: "Legmagasabb pont (m)", min: 0, max: 6000, step: 50, placeholder: "opcionális" },
];

export const goalForEvent = key => EVENT_CHOICES.find(item => item.key === key)?.kind === "hike" ? "Hegyi állóképesség" : "Futóteljesítmény";

/** `embedded`: the surrounding step already shows the question, so the legend is kept for screen readers only. */
export function GoalChooser({ value, onChange, embedded = false }) {
  const set = patch => onChange({ ...value, ...patch });
  const event = EVENT_CHOICES.find(item => item.key === value.eventType);
  const pickEvent = key => set({ eventType: key, goal: goalForEvent(key) });
  return <fieldset className="goal-chooser">
    <legend className={embedded ? "sr-only" : undefined}>Mire készülsz?</legend>
    {!embedded && <p className="goal-chooser-intro">Ha versenyre vagy túrára készülsz, válaszd ki, és a Garmin-adataidból hétről hétre felépítjük a felkészülést. Ha nem, válassz általános célt.</p>}
    <div className="event-choice-grid" role="radiogroup" aria-label="Esemény">
      {EVENT_CHOICES.map(item => <button type="button" role="radio" aria-checked={value.eventType === item.key} key={item.key} className={value.eventType === item.key ? "selected" : ""} onClick={() => pickEvent(item.key)}>
        {item.kind === "hike" ? <Mountain size={18} aria-hidden="true"/> : <Flag size={18} aria-hidden="true"/>}<b>{item.label}</b><small>{item.detail}</small></button>)}
      <button type="button" role="radio" aria-checked={!event} className={`event-choice-none ${!event ? "selected" : ""}`} onClick={() => set({ eventType: "" })}><b>Nincs konkrét eseményem</b><small>általános cél</small></button>
    </div>
    {event ? <div className="form-grid event-details">
      <div className="field"><label>Esemény neve (nem kötelező)</label><input aria-label="Esemény neve" value={value.eventName || ""} onChange={change => set({ eventName: change.target.value })} placeholder={event.kind === "hike" ? "Például: Mátrabérc" : "Például: Budapest Maraton"}/></div>
      <div className="field"><label>Esemény dátuma</label><input aria-label="Esemény dátuma" type="date" value={value.eventDate || ""} onChange={change => set({ eventDate: change.target.value })}/><small>Ebből tudjuk, hány hét van hátra.</small></div>
      {event.kind === "run" ? <div className="field wide"><label>Legutóbbi versenyidőd (nem kötelező)</label><div className="reference-race"><select aria-label="Referenciaverseny távja" value={value.referenceRaceKey || ""} onChange={change => set({ referenceRaceKey: change.target.value })}><option value="">Táv</option>{RACES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><input aria-label="Referenciaidő" value={value.referenceRaceTime || ""} onChange={change => set({ referenceRaceTime: change.target.value.trim() })} placeholder="óó:pp:mm vagy pp:mm" maxLength={8} pattern="(\d{1,2}:)?[0-5]?\d:[0-5]\d"/></div><small>Az elmúlt 6–8 hét legjobbja. Ebből számoljuk a tempóidat és a várható célidőt.</small></div>
        : <div className="field wide"><label>A túra adatai</label><div className="hike-fields">{HIKE_INPUTS.filter(item => !item.trekOnly || event.key === "trek").map(item => <label key={item.key}><span>{item.label}</span><input type="number" inputMode="decimal" min={item.min} max={item.max} step={item.step} value={value[item.key] ?? ""} onChange={change => set({ [item.key]: change.target.value === "" ? null : Number(change.target.value) })} placeholder={item.placeholder}/></label>)}</div><small>{event.key === "trek" ? "Egy átlagos túranap távja és szintemelkedése." : "A teljes túra távja és összes szintemelkedése."} A legmagasabb pontot elég 2000 m fölött megadni.</small></div>}
    </div>
    : <div className="choice-grid general-goal-grid" role="radiogroup" aria-label="Általános cél">{GENERAL_GOALS.map(([goal, detail]) => <button type="button" role="radio" aria-checked={value.goal === goal} key={goal} className={value.goal === goal ? "selected" : ""} onClick={() => set({ goal })}><b>{goal}</b><small>{detail}</small></button>)}</div>}
  </fieldset>;
}
