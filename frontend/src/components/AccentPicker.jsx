import { accentOptions } from "../lib/accents.js";

export function AccentPicker({value,onChange}){return <div className="accent-grid" role="radiogroup" aria-label="Akcentusszín">{accentOptions.map(option=><button type="button" role="radio" aria-checked={value===option.id} className={`accent-option ${value===option.id?"selected":""}`} style={{"--choice":option.color}} key={option.id} onClick={()=>onChange(option.id)}><i/><b>{option.name}</b></button>)}</div>}
