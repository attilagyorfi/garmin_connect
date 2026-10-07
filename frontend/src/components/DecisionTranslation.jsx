import { Search, Target, TrendingUp } from "lucide-react";

const ICONS=[TrendingUp,Search,Target];

// "What changed / why / what to do" for a period, with explicit loading, empty and error states.
export function DecisionTranslation({eyebrow,title,period,items,note,state="ready"}){const id=`${eyebrow.toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g,"-")}-title`;
  return <section className="card decision-translation" aria-labelledby={id}><div className="decision-translation-heading"><div><span className="eyebrow">{eyebrow}</span><h2 id={id}>{title}</h2></div><small>{period}</small></div>
    {state==="loading"?<p className="decision-translation-state">Az értelmezéshez szükséges adatok betöltése…</p>:state==="error"?<p className="decision-translation-state" role="alert">Az értelmezés most nem készíthető el. Nem helyettesítjük mintaadattal.</p>:state==="empty"?<p className="decision-translation-state">Még nincs értelmezhető szinkronizált előzmény.</p>
    :<><div className="decision-translation-grid">{items.map(([label,text],index)=>{const Icon=ICONS[index]||Target;return <article key={label}><Icon size={21} aria-hidden="true"/><span>{label}</span><p>{text}</p></article>})}</div><p className="decision-translation-note">{note}</p></>}</section>}
