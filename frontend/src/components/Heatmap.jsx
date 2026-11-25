import { heat } from "../lib/demoData.js";

export function Heatmap({values=heat}){return <div className="heatmap" aria-label="12 hét terhelése, napokra bontva">{values.map((v,i)=><i key={i} data-level={v}/>)}</div>}
