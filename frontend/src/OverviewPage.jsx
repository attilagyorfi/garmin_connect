import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { overviewData } from "./overviewData.js";
import "./overview.css";

const format = value => value == null ? "—" : value.toLocaleString("hu-HU", { maximumFractionDigits: 1 });
const dateLabel = value => new Date(`${value}T12:00:00Z`).toLocaleDateString("hu-HU");

export function OverviewPage({ profile }) {
  const [range, setRange] = useState(90);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState({ status: "loading", data: null });
  useEffect(() => {
    let controller;
    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      setResult({ status: "loading", data: null });
      try {
        const response = await fetch("/api/dashboard", { signal, cache: "no-store", credentials: "same-origin" });
        const body = await response.json();
        if (signal.aborted) return;
        if (response.status === 404 && body.code === "no_dashboard_data") {
          setResult({ status: "empty", data: null });
        } else if (!response.ok || !body || typeof body !== "object" || Array.isArray(body)) {
          setResult({ status: "error", data: null });
        } else setResult({ status: "ready", data: body });
      } catch { if (!signal.aborted) setResult({ status: "error", data: null }); }
    };
    load();
    window.addEventListener("hybrid-dashboard-refresh", load);
    return () => { controller?.abort(); window.removeEventListener("hybrid-dashboard-refresh", load); };
  }, [revision]);
  const model = overviewData(result.data, range);
  const available = result.status === "ready";
  const roundedMinutes = model.minutes == null ? null : Math.round(model.minutes);
  const strength = model.sessions.filter(item => item.type === "Erő").length;
  const kpis = [
    [available && model.known ? model.sessions.length : null, "Edzések", "darab", "Az időszakban rögzített összes edzés, a napi több alkalmat is külön számolva. A több edzés önmagában nem jelent jobb fejlődést."],
    [available && roundedMinutes != null ? `${Math.floor(roundedMinutes / 60)} ó ${roundedMinutes % 60} p` : null, "Edzésidő", "óra és perc", "A rögzített edzések összes időtartama. A hosszabb idő több mozgást jelent, de az intenzitás és a pihenés is számít."],
    [available ? model.load : null, "Összterhelés", "terhelési pont", "Az edzések számított terhelésének összege. Magasabb érték nagyobb összes terhelést jelez, nem feltétlenül jobb formát. Eltérő hosszúságú időszakokat nem érdemes közvetlenül összehasonlítani."],
    [available ? model.readiness : null, "Mai terhelhetőség", "pont / 100", "Becsült napi terhelhetőség, nem orvosi minősítés. A magasabb érték kedvezőbb regenerációs állapotra utalhat. Mai adat nélkül nem mutatunk korábbi pontszámot mainak."],
  ];
  return <div className="overview-page">
    <header className="overview-heading"><span className="eyebrow">TELJESÍTMÉNYKÉP</span><h1>Áttekintés</h1><p>A rögzített edzéseid és a számított terhelés alakulása.</p></header>
    <div className="overview-period"><div className="segmented" role="group" aria-label="Megjelenített időszak">{[[30,"30 nap"],[90,"90 nap"],[365,"1 év"]].map(([days,label]) => <button key={days} aria-pressed={range === days} className={range === days ? "active" : ""} onClick={() => setRange(days)}>{label}</button>)}</div><p>{dateLabel(model.from)} – {dateLabel(model.today)}</p></div>
    <div className="overview-data-state" role={result.status === "error" ? "alert" : "status"}>
      {result.status === "loading" && "A személyes adatok betöltése…"}
      {result.status === "empty" && "Még nincs szinkronizált adat. A jobb felső gombbal kösd össze a Garmin-fiókodat, majd indíts szinkronizálást."}
      {result.status === "error" && <>Az adatok betöltése nem sikerült. Ez nem jelenti azt, hogy nem volt edzésed. <button onClick={() => setRevision(value => value + 1)}>Újrapróbálás</button></>}
      {available && <>Adatforrás: a Garminból szinkronizált adatok és az alkalmazás számításai. {result.data.today && <>Az összesítés referencia-napja: {result.data.today}. </>}{result.data.today !== model.today && "Nincs mai összesítés; a mai terhelhetőség ezért nem látható."}</>}
    </div>
    <section className="overview-kpis" aria-label="Az időszak fő mutatói">{kpis.map(([value,label,unit,explanation]) => <div className="card" key={label}><span>{label}</span><strong>{typeof value === "string" ? value : format(value)}</strong><small>{unit}</small><p>{explanation}</p>{value == null && <small>Ehhez még nincs megfelelő adat.</small>}</div>)}</section>
    <section className="card overview-chart"><div className="section-head"><div><span className="eyebrow">FEJLŐDÉSTÖRTÉNET</span><h2>Edzettség, fáradtság és forma</h2></div></div>
      {available && model.points.length > 0 ? <ResponsiveContainer width="100%" height={350}><LineChart data={model.points} margin={{ top: 12, right: 24, bottom: 24, left: 38 }}><CartesianGrid stroke="#343635" vertical={false}/><XAxis dataKey="date" tickFormatter={dateLabel} fontSize={12} stroke="#b9bfbd" label={{ value: "Dátum (heti összesítés)", position: "insideBottom", offset: -18, fill: "#d5dad8" }}/><YAxis fontSize={12} stroke="#b9bfbd" label={{ value: "Terhelési pont", angle: -90, position: "insideLeft", offset: -24, fill: "#d5dad8" }}/><Tooltip labelFormatter={dateLabel} formatter={(value,name) => [`${format(value)} pont`, name]} contentStyle={{ background: "#181a19", border: "1px solid #555", color: "#fff" }}/><Legend verticalAlign="top"/><Line dataKey="ctl" name="Edzettség (CTL)" stroke="var(--accent)" strokeWidth={3} dot={model.points.length === 1}/><Line dataKey="atl" name="Fáradtság (ATL)" stroke="#f59e0b" strokeWidth={2} dot={model.points.length === 1}/><Line dataKey="tsb" name="Forma (TSB)" stroke="#60a5fa" strokeWidth={2} dot={model.points.length === 1}/></LineChart></ResponsiveContainer> : <p className="overview-empty">{result.status === "loading" ? "A grafikon betöltése…" : "Erre az időszakra nincs megjeleníthető trendadat. Nem helyettesítjük mintagrafikonnal."}</p>}
      <p>X tengely: dátum · Y tengely: terhelési pont. A grafikon heti átlagokat mutat, nem az egyes edzések terhelését. A hiányzó értékeket nem tekintjük nullának.</p>
      <div className="overview-explanations"><p><b>Edzettség (CTL):</b> a hosszabb távú terhelésből becsült edzettség. Emelkedése tartósabb edzésmunkát jelezhet, de önmagában nem bizonyít teljesítményjavulást.</p><p><b>Fáradtság (ATL):</b> a közelmúlt terhelésének rövid távú hatása. Gyors emelkedése nagyobb regenerációs igényt jelezhet.</p><p><b>Forma (TSB):</b> az edzettség és a fáradtság különbsége. Negatív értéknél a friss terhelés dominál; pozitív érték kipihentebb állapotra utalhat, de a tartós pihenés is növelheti.</p></div>
    </section>
    <section className="overview-bottom"><div className="card"><span className="eyebrow">EDZÉSMEGOSZLÁS</span><h2>{available && model.known ? `${strength} erőedzés · ${model.sessions.length - strength} egyéb edzés` : "Nincs megjeleníthető összesítés"}</h2><p>{available && model.known && model.sessions.length === 0 ? "A betöltött adatokban nincs edzés erre az időszakra. A szinkronizálás teljességét is érdemes ellenőrizni." : "Az alkalmak számát mutatjuk, nem az idő vagy a terhelés arányát. Egy nap több edzése külön-külön szerepel."}</p></div><div className="card"><span className="eyebrow">BEÁLLÍTOTT CÉLOD</span><h2>{profile?.goal || "Még nincs megadva"}</h2><p>Heti időkeret: {profile?.weeklyHours ?? "—"} óra · Erőedzés cél-aránya: {profile?.strengthRatio ?? "—"}%. Ezek tervezési beállítások, nem mért teljesítményadatok.</p></div></section>
  </div>;
}
