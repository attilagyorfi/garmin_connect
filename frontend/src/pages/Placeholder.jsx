import { BarChart3 } from "lucide-react";
import { PageHeader } from "../components/PageHeader.jsx";

export function Placeholder({page}){return <><PageHeader eyebrow="HYBRID ATHLETE" title={page}/><div className="placeholder card"><BarChart3 size={26}/><h2>{page}</h2><p>Ez a nézet a következő migrációs lépésben kapja meg a végleges felületét.</p></div></>}
