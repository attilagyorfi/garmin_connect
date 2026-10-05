import { heat } from "../lib/demoData.js";

export function Heatmap({values=heat}){return <div className="heatmap" aria-label="12 hetes terhelési hőtérkép">{values.map((v,i)=><i key={i} data-level={v}/>)}</div>}
