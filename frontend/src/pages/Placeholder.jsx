import { BarChart3 } from "lucide-react";
import { PageHeader } from "../components/PageHeader.jsx";

export function Placeholder({page}){return <><PageHeader eyebrow="HYBRID ATHLETE" title={page}/><div className="placeholder card"><BarChart3 size={26}/><h2>{page}</h2><p>Ezen az oldalon most nincs mit mutatni. Válassz másikat a menüből.</p></div></>}
