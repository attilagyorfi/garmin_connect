import { useEffect, useState } from "react";

const SCALES=[["soreness","Izomláz","nincs","erős"],["fatigue","Fáradtság","friss vagyok","kimerült vagyok"],["motivation","Motiváció","nincs kedvem","nagyon motivált vagyok"],["stress","Stressz","nyugodt vagyok","nagyon feszült vagyok"]];
const emptyCheckin={soreness:2,fatigue:2,motivation:4,stress:2,pain:false,illness:false,note:""};
const answeredFrom=value=>new Set(value?.savedAt?SCALES.map(([key])=>key):[]);

// Daily self-report. In `required` mode every scale must be answered before the recommendation is computed;
// a scale only counts as answered once the user picked a value, so defaults are never saved silently.
export function CheckIn({value,onSave,required=false}){const [values,setValues]=useState(value||emptyCheckin),[saved,setSaved]=useState(Boolean(value?.savedAt)),[answered,setAnswered]=useState(()=>answeredFrom(value));
  useEffect(()=>{setValues(value||emptyCheckin);setSaved(Boolean(value?.savedAt));setAnswered(answeredFrom(value))},[value]);
  const set=(key,next)=>{setValues(current=>({...current,[key]:next}));setSaved(false);if(SCALES.some(([scale])=>scale===key))setAnswered(current=>new Set([...current,key]))},complete=answered.size===SCALES.length;
  const row=([key,label,low,high])=><div className="scale-row" key={key}><div className="scale-row-head"><span>{label}</span><small>{`1 · ${low}  —  5 · ${high}`}</small></div><div className="scale-buttons" role="group" aria-label={`${label}: 1 ${low}, 5 ${high}`}>{[1,2,3,4,5].map(n=>{const on=answered.has(key)&&values[key]===n;return <button key={n} type="button" aria-label={`${label}: ${n} az 5-ből`} aria-pressed={on} className={on?"selected":""} onClick={()=>set(key,n)}>{n}</button>})}</div></div>;
  return <section className={`card checkin ${required&&!saved?"checkin-required":""}`}><div className="section-head"><div><span className="eyebrow">GYORS ÁLLAPOTFELMÉRÉS</span><p>{required&&!saved?"Válaszolj mind a négy kérdésre, hogy a Garmin-adatokkal együtt személyes javaslatot készíthessünk.":"Adj rövid kontextust a mai döntéshez."}</p></div><small>{saved?`MENTVE · ${new Date(values.savedAt).toLocaleTimeString("hu-HU",{hour:"2-digit",minute:"2-digit"})}`:`${answered.size} / ${SCALES.length} KITÖLTVE`}</small></div>
    <div className="check-grid">{SCALES.map(row)}</div>
    <div className="check-alerts"><button type="button" aria-pressed={values.pain} className={values.pain?"selected":""} onClick={()=>set("pain",!values.pain)}>Fájdalmat érzek</button><button type="button" aria-pressed={values.illness} className={values.illness?"selected":""} onClick={()=>set("illness",!values.illness)}>Betegségérzetem van</button></div>
    <p className="check-alert-help">A fájdalom vagy betegségérzet biztonsági jelzés: csökkentheti vagy pihenőnapra módosíthatja a mai javaslatot.</p>
    <div className="check-footer"><input value={values.note} onChange={event=>set("note",event.target.value)} placeholder="Megjegyzés (nem kötelező)" aria-label="Megjegyzés"/><button disabled={required&&!complete} onClick={()=>{const next={...values,savedAt:new Date().toISOString()};setValues(next);setSaved(true);onSave(next)}}>{saved?"Elmentve":"Mentés és a javaslat kiszámítása"}</button></div></section>}
