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
    ? `${dateLabel(dataQuality.activityDateFrom)} – ${dateLabel(dataQuality.activityDateTo)}.`
    : "A történeti időszak még nem ismert.";
  const freshnessCurrent = available && result.data?.today === model.today;
  const loadExplanation = allLoadsOfficial
    ? "A Garmin által edzésenként számított aktivitási terhelések összege. Magasabb érték nagyobb összes fiziológiai terhelést jelez, nem feltétlenül jobb formát. Eltérő hosszúságú időszakokat nem érdemes közvetlenül összehasonlítani."
    : `Hybrid Athlete-becslés, mert az időszak edzéseinek nem mindegyikéhez érkezett Garmin aktivitási terhelés${model.sessions.length ? ` (Garmin-lefedettség: ${officialLoadCoverage}%)` : ""}. Ez nem Garmin Training Load.`;
  const readinessExplanation = readinessOfficial
    ? "A Garmin 0–100 közötti Training Readiness értéke. A Garmin többek között az alvást, a regenerációs időt, a HRV-állapotot, az akut terhelést és a stresszelőzményt használja hozzá; ez nem orvosi minősítés."
    : "Hybrid Athlete által becsült napi terhelhetőség, nem Garmin Training Readiness és nem orvosi minősítés. Mai adat nélkül nem mutatunk korábbi pontszámot mainak.";
  const kpis = [
    [available && model.known ? model.sessions.length : null, "Edzések", "darab", "Az aktivitásaid gyakoriságát mutatja.", "Az időszakban rögzített összes edzés, a napi több alkalmat is külön számolva. A több edzés önmagában nem jelent jobb fejlődést."],
    [available && roundedMinutes != null ? `${Math.floor(roundedMinutes / 60)} ó ${roundedMinutes % 60} p` : null, "Edzésidő", "óra és perc", "A mozgással töltött összes idő.", "A rögzített edzések összes időtartama. A hosszabb idő több mozgást jelent, de az intenzitás és a pihenés is számít."],
    [available ? model.load : null, "Összterhelés", "terhelési pont", "Az időszak összes fiziológiai terhelése.", loadExplanation],
    [available ? model.readiness : null, readinessOfficial ? "Garmin Training Readiness" : "Mai terhelhetőség", "pont / 100", "A mai edzésvállalás becsült kerete.", readinessExplanation],
  ];
  const syncLabel = syncing ? `${Math.round(job?.progress || 0)}%` : resumeRunId ? "SZINKRON FOLYTATÁSA" : "SZINKRON";
  return <><PageHeader eyebrow="TELJESÍTMÉNYKÉP" title="Áttekintés"><div className="header-actions"><span>{syncError || "A rögzített edzéseid és a számított terhelés alakulása."}</span><button onClick={() => syncNow(resumeRunId)} disabled={syncing}>{syncing ? <AnimatedBrandMark className="sync-brand-mark" /> : <RefreshCw size={14} />} {syncLabel}</button></div></PageHeader>
  <main className="overview-page">
    <div className="overview-period"><div className="segmented" role="group" aria-label="Megjelenített időszak">{[[30, "30 nap"], [90, "90 nap"], [365, "1 év"]].map(([days, label]) => <button key={days} aria-pressed={range === days} className={range === days ? "active" : ""} onClick={() => setRange(days)}>{label}</button>)}</div><p>{dateLabel(model.from)} – {dateLabel(model.today)}</p></div>
    <div className="overview-data-state" role={result.status === "error" ? "alert" : "status"}>
      {result.status === "loading" && "A személyes adatok betöltése…"}
      {result.status === "empty" && "Még nincs szinkronizált adat. A Beállításokban kösd össze a Garmin-fiókodat, majd indíts szinkronizálást."}
      {result.status === "error" && <>Az adatok betöltése nem sikerült. Ez nem jelenti azt, hogy nem volt edzésed. <button onClick={() => setRevision(value => value + 1)}>Újrapróbálás</button></>}
      {available && <>Adatforrás: Garmin-mérések és külön jelölt Hybrid Athlete-számítások. {result.data.today && <>Az összesítés referencianapja: {dateLabel(result.data.today)}. </>}{result.data.today !== model.today && "Nincs mai összesítés; a mai terhelhetőség ezért nem látható."}</>}
    </div>
    <section className="overview-kpis" aria-label="Az időszak fő mutatói">{kpis.map(([value, label, unit, summary, explanation]) => <div className="card" key={label}><span>{label}</span><strong>{typeof value === "string" ? value : format(value)}</strong><small>{unit}</small><p className="overview-kpi-summary">{summary}</p>{value == null && <small>Ehhez még nincs megfelelő adat.</small>}<details className="overview-kpi-details"><summary>Mit jelent ez</summary><p>{explanation}</p></details></div>)}</section>
    <section className="card overview-quality" aria-labelledby="overview-quality-title">
      <div className="section-head"><div><span className="eyebrow">ADATMINŐSÉG ÉS LEFEDETTSÉG</span><h2 id="overview-quality-title">Mennyire teljes az értékelés alapja?</h2></div></div>
      <p className="overview-quality-intro">Itt nem újabb teljesítménypontszámot adunk. Azt mutatjuk meg, mely adatok állnak rendelkezésre, és hol használ a rendszer saját, külön jelölt becslést.</p>
      <div className="overview-quality-grid">
        <article data-state={freshnessCurrent ? "good" : "limited"}><span>Frissesség</span><strong>{available ? (freshnessCurrent ? "Mai adat elérhető" : `Utolsó adat: ${result.data?.today ? dateLabel(result.data.today) : "nem ismert"}`) : "Nem ellenőrizhető"}</strong><p>{freshnessCurrent ? "A napi értelmezés a mai Garmin-összesítésből készül." : "A terhelhetőséget ne kezeld mai állapotként, amíg nincs friss szinkron."}</p></article>
        <article data-state={dailySignalCount === SIGNALS ? "good" : "limited"}><span>Napi állapotjelek</span><strong>{dailySignalCount == null ? "Nem ismert" : `${dailySignalCount} / ${SIGNALS} elérhető`}</strong><p>{missingMetrics.length ? `Hiányzik: ${missingMetrics.join(", ")}. A rendszer a meglévő jelek súlyát arányosan kezeli.` : dataQuality ? "A HRV, az alvás, a nyugalmi pulzus és a hibrid TSB rendelkezésre áll." : "A forrás nem adott részletes lefedettségi információt."}</p></article>
        <article data-state={model.sessions.length && officialLoadCoverage === 100 ? "good" : "mixed"}><span>Edzésterhelés forrása</span><strong>{model.sessions.length ? `${officialLoadCoverage}% Garmin-adat` : "Nincs edzés az időszakban"}</strong><p>{model.sessions.length ? (officialLoadCoverage === 100 ? "Minden kiválasztott edzéshez Garmin által átadott aktivitási terhelést használunk." : officialLoadCoverage === 0 ? "Az időszak edzéseihez az óra nem adott terhelési értéket, ezért külön jelölt Hybrid Athlete-becslést használunk." : `A fennmaradó ${100 - officialLoadCoverage}%-nál külön jelölt Hybrid Athlete-becslés egészíti ki az összesítést.`) : "Terhelési lefedettség csak rögzített edzéseknél számítható."}</p></article>
        <article data-state={activityCount ? "good" : "limited"}><span>Történeti mélység</span><strong>{activityCount == null ? "Nem ismert" : `${activityCount.toLocaleString("hu-HU")} edzés`}</strong><p>{historyRange} A hosszabb előtörténet stabilabb személyes viszonyítási alapot ad.</p></article>
      </div>
      <p className="overview-quality-note"><b>Hogyan értelmezd?</b> A hiányzó adat nem nulla. Kevesebb vagy vegyes forrású adatnál az ajánlás óvatosabb, és minden saját számítás Hybrid Athlete-becslésként jelenik meg.</p>
    </section>
    <section className="card overview-chart"><div className="section-head"><div><span className="eyebrow">FEJLŐDÉSTÖRTÉNET · HYBRID ATHLETE</span><h2>Becsült edzettség, fáradtság és forma</h2></div></div>
      {available && model.points.length > 0 ? <ResponsiveContainer width="100%" height={350}><LineChart data={model.points} margin={{ top: 12, right: 24, bottom: 24, left: 38 }}><CartesianGrid stroke="#343635" vertical={false} /><XAxis dataKey="date" tickFormatter={dateLabel} fontSize={12} stroke="#b9bfbd" label={{ value: "Dátum (heti összesítés)", position: "insideBottom", offset: -18, fill: "#d5dad8" }} /><YAxis fontSize={12} stroke="#b9bfbd" label={{ value: "Hybrid terhelési pont", angle: -90, position: "insideLeft", offset: -24, fill: "#d5dad8" }} /><Tooltip labelFormatter={dateLabel} formatter={(value, name) => [`${format(value)} pont`, name]} contentStyle={{ background: "#181a19", border: "1px solid #555", color: "#fff" }} /><Legend verticalAlign="top" /><Line dataKey="ctl" name="Hybrid edzettség (CTL)" stroke="var(--accent)" strokeWidth={3} dot={model.points.length === 1} /><Line dataKey="atl" name="Hybrid fáradtság (ATL)" stroke="#f59e0b" strokeWidth={2} dot={model.points.length === 1} /><Line dataKey="tsb" name="Hybrid forma (TSB)" stroke="#60a5fa" strokeWidth={2} dot={model.points.length === 1} /></LineChart></ResponsiveContainer> : <p className="overview-empty">{result.status === "loading" ? "A grafikon betöltése…" : "Erre az időszakra nincs megjeleníthető trendadat. Nem helyettesítjük mintagrafikonnal."}</p>}
      <p>X tengely: dátum · Y tengely: Hybrid terhelési pont. A grafikon heti átlagokat mutat, nem az egyes edzések terhelését. A hiányzó értékeket nem tekintjük nullának.</p>
      <details className="overview-chart-details"><summary>Mit jelentenek a görbék</summary><p>A CTL/ATL/TSB itt saját teljesítménymenedzsment-becslés, nem a Garmin Training Load vagy Training Status.</p><div className="overview-explanations"><p><b>Hybrid edzettség (CTL):</b> a hosszabb távú terhelésből becsült edzettség. Emelkedése tartósabb edzésmunkát jelezhet, de önmagában nem bizonyít teljesítményjavulást.</p><p><b>Hybrid fáradtság (ATL):</b> a közelmúlt terhelésének rövid távú becslése. Gyors emelkedése nagyobb regenerációs igényt jelezhet.</p><p><b>Hybrid forma (TSB):</b> a becsült edzettség és fáradtság különbsége. Negatív értéknél a friss terhelés dominál; pozitív érték kipihentebb állapotra utalhat, de a tartós pihenés is növelheti.</p></div></details>
    </section>
    <section className="overview-bottom"><div className="card"><span className="eyebrow">EDZÉSMEGOSZLÁS</span><h2>{available && model.known ? `${strength} erőedzés · ${model.sessions.length - strength} egyéb edzés` : "Nincs megjeleníthető összesítés"}</h2><p>{available && model.known && model.sessions.length === 0 ? "A betöltött adatokban nincs edzés erre az időszakra. A szinkronizálás teljességét is érdemes ellenőrizni." : "Az alkalmak számát mutatjuk, nem az idő vagy a terhelés arányát. Egy nap több edzése külön-külön szerepel."}</p></div><div className="card"><span className="eyebrow">BEÁLLÍTOTT CÉLOD</span><h2>{profile?.goal || "Még nincs megadva"}</h2><p>Heti időkeret: {profile?.weeklyHours ?? "—"} óra · Erőedzés cél-aránya: {profile?.strengthRatio ?? "—"}%. Ezek tervezési beállítások, nem mért teljesítményadatok.</p></div></section>
  </main></>;
}
