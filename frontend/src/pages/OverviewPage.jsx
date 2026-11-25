import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AnimatedBrandMark } from "../components/Brand.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { overviewData } from "../lib/overviewData.js";
import { useGarminSync } from "../lib/useGarminSync.js";

const format = value => value == null ? "—" : value.toLocaleString("hu-HU", { maximumFractionDigits: 1 });
const dateLabel = value => new Date(`${value}T12:00:00Z`).toLocaleDateString("hu-HU");
const SIGNALS = 4;

// Period summary of the synced history. Loading, empty, stale and failed data are kept apart:
// a missing value is never shown as zero and no sample chart replaces personal data.
export function OverviewPage({ profile, onDataChanged }) {
  const [range, setRange] = useState(90);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState({ status: "loading", data: null });
  const { syncing, job, error: syncError, start: syncNow, resumeRunId } = useGarminSync({ onCompleted: async () => { setRevision(value => value + 1); await onDataChanged?.(); } });
  useEffect(() => {
    const controller = new AbortController();
    setResult({ status: "loading", data: null });
    fetch("/api/dashboard", { signal: controller.signal, cache: "no-store", credentials: "same-origin" })
      .then(async response => {
        const body = await response.json().catch(() => null);
        if (response.status === 404 && body?.code === "no_dashboard_data") setResult({ status: "empty", data: null });
        else if (!response.ok || !body || typeof body !== "object" || Array.isArray(body)) setResult({ status: "error", data: null });
        else setResult({ status: "ready", data: body });
      })
      .catch(() => { if (!controller.signal.aborted) setResult({ status: "error", data: null }); });
    return () => controller.abort();
  }, [revision]);
  const model = overviewData(result.data, range);
  const available = result.status === "ready";
  const roundedMinutes = model.minutes == null ? null : Math.round(model.minutes);
  const strength = model.sessions.filter(item => item.type === "Erő").length;
  const officialLoadCount = model.sessions.filter(item => item.loadSource === "garmin_activity_training_load").length;
  const officialLoadCoverage = model.sessions.length ? Math.round(officialLoadCount / model.sessions.length * 100) : 0;
  const allLoadsOfficial = model.sessions.length > 0 && officialLoadCoverage === 100;
  const readinessOfficial = result.data?.readinessSource === "garmin_training_readiness";
  const dataQuality = result.data?.dataQuality && typeof result.data.dataQuality === "object" ? result.data.dataQuality : null;
  const missingMetrics = Array.isArray(dataQuality?.missingMetrics) ? dataQuality.missingMetrics : [];
  const dailySignalCount = dataQuality ? Math.max(0, SIGNALS - missingMetrics.length) : null;
  const activityCount = Number.isFinite(dataQuality?.activityCount) ? dataQuality.activityCount : null;
  const historyRange = dataQuality?.activityDateFrom && dataQuality?.activityDateTo
    ? `${dateLabel(dataQuality.activityDateFrom)} – ${dateLabel(dataQuality.activityDateTo)}`
    : "Az időszak még nem ismert.";
  const freshnessCurrent = available && result.data?.today === model.today;
  const loadExplanation = allLoadsOfficial
    ? "A Garmin edzésenként számolt terheléseinek összege. A nagyobb szám nagyobb terhelést jelez a szervezetednek, nem feltétlenül jobb formát. Eltérő hosszú időszakokat ne hasonlíts össze közvetlenül."
    : `Hybrid Athlete-becslés, mert az időszakban nem minden edzéshez érkezett terhelés a Garmintól${model.sessions.length ? ` (Garmin-adat: ${officialLoadCoverage}%)` : ""}. Ez nem Garmin Training Load.`;
  const readinessExplanation = readinessOfficial
    ? "A Garmin 0–100 közötti Training Readiness értéke. Többek között az alvásból, a regenerációs időből, a HRV-állapotból (szívverések közötti idő ingadozása), a friss terhelésből és a korábbi stresszből számolja. Ez nem orvosi minősítés."
    : "A Hybrid Athlete becslése a mai terhelhetőségedről, nem Garmin Training Readiness és nem orvosi minősítés. Mai adat nélkül nem mutatunk korábbi pontszámot mainak.";
  const kpis = [
    [available && model.known ? model.sessions.length : null, "Edzések", "darab", "Ennyiszer edzettél az időszakban.", "Az időszak összes rögzített edzése. Ha egy nap többször edzettél, mindet külön számoljuk. A több edzés önmagában nem jelent nagyobb fejlődést."],
    [available && roundedMinutes != null ? `${Math.floor(roundedMinutes / 60)} ó ${roundedMinutes % 60} p` : null, "Edzésidő", "óra és perc", "Ennyi időt töltöttél mozgással.", "A rögzített edzéseid összes ideje. A hosszabb idő több mozgás, de az intenzitás és a pihenés is számít."],
    [available ? model.load : null, "Összterhelés", "terhelési pont", "Ennyi terhelés érte a szervezeted.", loadExplanation],
    [available ? model.readiness : null, readinessOfficial ? "Garmin Training Readiness" : "Mai terhelhetőség", "pont / 100", "Becslés arról, mennyit bírsz ma.", readinessExplanation],
  ];
  const syncLabel = syncing ? `${Math.round(job?.progress || 0)}%` : resumeRunId ? "Szinkron folytatása" : "Szinkron";
  return <><PageHeader eyebrow="HOGY ÁLLSZ MOST" title="Áttekintés"><div className="header-actions"><span>{syncError || "Az edzéseid, és hogyan alakul a számolt terhelésed."}</span><button onClick={() => syncNow(resumeRunId)} disabled={syncing}>{syncing ? <AnimatedBrandMark className="sync-brand-mark" /> : <RefreshCw size={14} />} {syncLabel}</button></div></PageHeader>
  <div className="overview-page">
    <div className="overview-period"><div className="segmented" role="group" aria-label="Megjelenített időszak">{[[30, "30 nap"], [90, "90 nap"], [365, "1 év"]].map(([days, label]) => <button key={days} aria-pressed={range === days} className={range === days ? "active" : ""} onClick={() => setRange(days)}>{label}</button>)}</div><p>{dateLabel(model.from)} – {dateLabel(model.today)}</p></div>
    <div className="overview-data-state" role={result.status === "error" ? "alert" : "status"}>
      {result.status === "loading" && "Töltjük az adataidat…"}
      {result.status === "empty" && "Még nincs szinkronizált adat. A Beállításokban kösd össze a Garmin-fiókodat, majd indíts szinkront."}
      {result.status === "error" && <>Nem sikerült betölteni az adatokat. Ez nem jelenti azt, hogy nem volt edzésed. <button onClick={() => setRevision(value => value + 1)}>Próbáld újra</button></>}
      {available && <>Adatforrás: Garmin-mérések és külön jelölt Hybrid Athlete-számítások. {result.data.today && <>Utolsó adat napja: {dateLabel(result.data.today)} </>}{result.data.today !== model.today && "Mai adat nincs, ezért a mai terhelhetőség sem látszik."}</>}
    </div>
    <section className="overview-kpis" aria-label="Az időszak fő mutatói">{kpis.map(([value, label, unit, summary, explanation]) => <div className="card" key={label}><span>{label}</span><strong>{typeof value === "string" ? value : format(value)}</strong><small>{unit}</small><p className="overview-kpi-summary">{summary}</p>{value == null && <small>Ehhez még nincs megfelelő adat.</small>}<details className="overview-kpi-details"><summary>Mit jelent ez</summary><p>{explanation}</p></details></div>)}</section>
    <section className="card overview-quality" aria-labelledby="overview-quality-title">
      <div className="section-head"><div><span className="eyebrow">MILYEN ADATBÓL SZÁMOLUNK</span><h2 id="overview-quality-title">Mennyire teljesek az adataid?</h2></div></div>
      <p className="overview-quality-intro">Ez nem újabb pontszám a teljesítményedről. Itt látod, melyik adatod van meg, és hol használunk saját, külön jelölt becslést.</p>
      <div className="overview-quality-grid">
        <article data-state={freshnessCurrent ? "good" : "limited"}><span>Friss az adat?</span><strong>{available ? (freshnessCurrent ? "Van mai adat" :`Utolsó adat: ${result.data?.today ? dateLabel(result.data.today) : "nem ismert"}`) : "Most nem tudjuk"}</strong><p>{freshnessCurrent ? "A mai értékelés a mai Garmin-adatokból készül." : "Amíg nincs friss szinkron, a terhelhetőséget ne vedd mai állapotnak."}</p></article>
        <article data-state={dailySignalCount === SIGNALS ? "good" : "limited"}><span>Napi mutatók</span><strong>{dailySignalCount == null ? "Nem ismert" : `${dailySignalCount} / ${SIGNALS} elérhető`}</strong><p>{missingMetrics.length ? `Hiányzik: ${missingMetrics.join(", ")}. A meglévőket arányosan súlyozzuk.` : dataQuality ? "Megvan a HRV (szívverések közötti idő ingadozása), az alvás, a nyugalmi pulzus és a hibrid TSB (becsült forma) is." : "Nem kaptunk róla részletes adatot, melyik van meg."}</p></article>
        <article data-state={model.sessions.length && officialLoadCoverage === 100 ? "good" : "mixed"}><span>Edzésterhelés forrása</span><strong>{model.sessions.length ? `${officialLoadCoverage}% Garmin-adat` : "Nincs edzés az időszakban"}</strong><p>{model.sessions.length ? (officialLoadCoverage === 100 ? "Az időszak minden edzésénél a Garmin edzésenként számolt terhelését használjuk." : officialLoadCoverage === 0 ? "Az órád az időszak edzéseihez nem adott terhelést, ezért külön jelölt Hybrid Athlete-becslést használunk." : `A maradék ${100 - officialLoadCoverage}%-nál külön jelölt Hybrid Athlete-becsléssel számolunk.`) : "Arányt csak rögzített edzésekből tudunk számolni."}</p></article>
        <article data-state={activityCount ? "good" : "limited"}><span>Előzmény</span><strong>{activityCount == null ? "Nem ismert" : `${activityCount.toLocaleString("hu-HU")} edzés`}</strong><p>{historyRange} Minél több az előzmény, annál biztosabb, mi a megszokott nálad.</p></article>
      </div>
      <p className="overview-quality-note"><b>Hogyan olvasd?</b> A hiányzó adat nem nulla. Ha kevesebb az adat vagy vegyes a forrása, óvatosabb a javaslat. Minden saját számításnál kiírjuk, hogy Hybrid Athlete-becslés.</p>
    </section>
    <section className="card overview-chart"><div className="section-head"><div><span className="eyebrow">HOGYAN FEJLŐDSZ · HYBRID ATHLETE</span><h2>Becsült edzettség, fáradtság és forma</h2></div></div>
      {available && model.points.length > 0 ? <ResponsiveContainer width="100%" height={350}><LineChart data={model.points} margin={{ top: 12, right: 24, bottom: 24, left: 38 }}><CartesianGrid stroke="#343635" vertical={false} /><XAxis dataKey="date" tickFormatter={dateLabel} fontSize={12} stroke="#b9bfbd" label={{ value: "Dátum (heti átlag)", position: "insideBottom", offset: -18, fill: "#d5dad8" }} /><YAxis fontSize={12} stroke="#b9bfbd" label={{ value: "Hybrid terhelési pont", angle: -90, position: "insideLeft", offset: -24, fill: "#d5dad8" }} /><Tooltip labelFormatter={dateLabel} formatter={(value, name) => [`${format(value)} pont`, name]} contentStyle={{ background: "#181a19", border: "1px solid #555", color: "#fff" }} /><Legend verticalAlign="top" /><Line dataKey="ctl" name="Hybrid edzettség (CTL)" stroke="var(--accent)" strokeWidth={3} dot={model.points.length === 1} /><Line dataKey="atl" name="Hybrid fáradtság (ATL)" stroke="#f59e0b" strokeWidth={2} dot={model.points.length === 1} /><Line dataKey="tsb" name="Hybrid forma (TSB)" stroke="#60a5fa" strokeWidth={2} dot={model.points.length === 1} /></LineChart></ResponsiveContainer> : <p className="overview-empty">{result.status === "loading" ? "Töltjük a grafikont…" : "Erre az időszakra nincs adat a grafikonhoz. Nem mutatunk helyette mintagrafikont."}</p>}
      <p>Vízszintesen a dátum, függőlegesen a Hybrid terhelési pont. A grafikon heti átlagokat mutat, nem az egyes edzések terhelését. A hiányzó érték nem nulla.</p>
      <details className="overview-chart-details"><summary>Mit jelentenek a görbék</summary><p>A CTL, az ATL és a TSB itt a saját becslésünk, nem a Garmin Training Load vagy Training Status.</p><div className="overview-explanations"><p><b>Hybrid edzettség (CTL):</b> a hosszabb távú terhelésből becsült edzettség. Ha emelkedik, kitartóbban edzhettél, de ez önmagában nem bizonyítja, hogy javult a teljesítményed.</p><p><b>Hybrid fáradtság (ATL):</b> a közelmúlt terheléséből becsült rövid távú fáradtság. Ha gyorsan nő, több pihenés kellhet.</p><p><b>Hybrid forma (TSB):</b> a becsült edzettség és fáradtság különbsége. Ha negatív, a friss terhelés van túlsúlyban. Ha pozitív, kipihentebb lehetsz, de a tartós pihenés is növelheti.</p></div></details>
    </section>
    <section className="overview-bottom"><div className="card"><span className="eyebrow">MIT EDZETTÉL</span><h2>{available && model.known ? `${strength} erőedzés · ${model.sessions.length - strength} egyéb edzés` : "Most nincs összesítés"}</h2><p>{available && model.known && model.sessions.length === 0 ? "A betöltött adatokban nincs edzés erre az időszakra. Nézd meg azt is, végigment-e a szinkron." : "Az edzések számát mutatjuk, nem az idő vagy a terhelés arányát. Ha egy nap többször edzettél, mindet külön számoljuk."}</p></div><div className="card"><span className="eyebrow">A CÉLOD</span><h2>{profile?.goal || "Még nincs megadva"}</h2><p>Heti időkeret: {profile?.weeklyHours ?? "—"} óra · Erőedzés célaránya: {profile?.strengthRatio ?? "—"}%. Ezek a beállításaid, nem mért adatok.</p></div></section>
  </div></>;
}
