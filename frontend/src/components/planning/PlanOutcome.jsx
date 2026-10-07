import { useMemo, useState } from "react";
import { CalendarDays, ChevronRight, ClipboardList, Sparkles, Target } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricHelp } from "../Explainability.jsx";
import { budapestToday } from "../../lib/overviewData.js";
import { formatMinutes } from "../../lib/periods.js";
import { buildPlanOutcomeHistory, buildWeeklyClosure } from "../../lib/planOutcomes.js";

export function PlanOutcomeHistory({
  plans = [],
  activities = [],
  feedback = {},
  loading = false,
}) {
  const [weekCount, setWeekCount] = useState(8),
    history = useMemo(
      () =>
        buildPlanOutcomeHistory(
          plans,
          activities,
          feedback,
          budapestToday(),
          weekCount,
        ),
      [plans, activities, feedback, weekCount],
    );
  return (
    <section
      className="plan-outcome-history card"
      aria-labelledby="plan-outcome-title"
    >
      <header className="plan-outcome-head">
        <div>
          <span className="eyebrow">FEJLŐDÉSTÖRTÉNET</span>
          <h2 id="plan-outcome-title">Terv és tény alakulása</h2>
          <p>
            A tervezett munkát, a tényleges Garmin-edzéseket és a saját
            terhelésérzetedet hetenként, azonos logika szerint vetjük össze.
          </p>
        </div>
        <div className="plan-history-range" aria-label="Vizsgált időszak">
          {[4, 8, 12].map((count) => (
            <button
              key={count}
              className={weekCount === count ? "active" : ""}
              aria-pressed={weekCount === count}
              onClick={() => setWeekCount(count)}
            >
              {count} HÉT
            </button>
          ))}
        </div>
      </header>
      {loading ? (
        <p className="plan-history-empty">A fejlődéstörténet betöltése…</p>
      ) : !history.dataWeeks.length ? (
        <p className="plan-history-empty">
          Még nincs terv vagy edzés ebben az időszakban. A többhetes
          összevetés az első rögzített hét után jelenik meg.
        </p>
      ) : (
        <>
          <div className="plan-history-metrics">
            <article>
              <strong>
                {history.plannedWeekCount
                  ? formatMinutes(history.plannedTotal)
                  : "—"}
              </strong>
              <MetricHelp
                term="Tervezett edzésidő"
                text="A kiválasztott időszakban előre rögzített edzéspercek összege. Ez a vállalás, nem az elvégzett munka."
              >
                <b>TERVEZETT IDŐ</b>
              </MetricHelp>
              <small>
                {history.plannedWeekCount
                  ? `${history.plannedWeekCount} tervezett hét vállalása.`
                  : "Ebben az időszakban nincs rögzített tervadat."}
              </small>
            </article>
            <article>
              <strong>{formatMinutes(history.actualTotal)}</strong>
              <MetricHelp
                term="Tényleges edzésidő"
                text="A Garminból érkezett összes aktivitás ideje az adott hetekben, a nem tervezett edzéseket is beleértve."
              >
                <b>TÉNYLEGES IDŐ</b>
              </MetricHelp>
              <small>Minden szinkronizált aktivitással együtt.</small>
            </article>
            <article>
              <strong>
                {history.averageAdherence === null
                  ? "—"
                  : `${history.averageAdherence}%`}
              </strong>
              <MetricHelp
                term="Átlagos tervkövetés"
                text="A lezárt, tervezett hetekben teljesített edzések aránya. A futó hetet és a terv nélküli heteket nem számítjuk bele."
              >
                <b>ÁTLAGOS TERVKÖVETÉS</b>
              </MetricHelp>
              <small>
                {history.comparableWeeks.length
                  ? `${history.comparableWeeks.length} összevethető lezárt hét alapján.`
                  : "Még nincs lezárt, összevethető hét."}
              </small>
            </article>
            <article>
              <strong>
                {history.feedbackCoverage === null
                  ? "—"
                  : `${history.feedbackCoverage}%`}
              </strong>
              <MetricHelp
                term="RPE-lefedettség"
                text="Megmutatja, az aktivitások mekkora részéhez rögzítettél szubjektív nehézséget. A hiányzó RPE nem nulla terhelést jelent."
              >
                <b>RPE-LEFEDETTSÉG</b>
              </MetricHelp>
              <small>Minél teljesebb, annál biztosabb az értelmezés.</small>
            </article>
          </div>
          <div
            className="plan-history-chart"
            role="img"
            aria-label="Heti tervezett és tényleges edzésidő oszlopdiagramja percben"
          >
            <ResponsiveContainer width="100%" height={290}>
              <BarChart
                data={history.weeks}
                margin={{ top: 12, right: 18, left: 12, bottom: 28 }}
              >
                <CartesianGrid stroke="#303231" strokeDasharray="3 4" />
                <XAxis
                  dataKey="label"
                  stroke="#8d9490"
                  tick={{ fontSize: 11 }}
                  label={{
                    value: "Hét kezdete",
                    position: "insideBottom",
                    offset: -18,
                    fill: "#9da39f",
                    fontSize: 11,
                  }}
                />
                <YAxis
                  stroke="#8d9490"
                  tick={{ fontSize: 11 }}
                  width={58}
                  label={{
                    value: "Edzésidő (perc)",
                    angle: -90,
                    position: "insideLeft",
                    fill: "#9da39f",
                    fontSize: 11,
                  }}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,.035)" }}
                  formatter={(value, name) => [
                    `${Number(value).toLocaleString("hu-HU")} perc`,
                    name,
                  ]}
                  labelFormatter={(label) => `Hét kezdete: ${label}`}
                  contentStyle={{
                    background: "#171918",
                    border: "1px solid #3a3d3b",
                    borderRadius: 8,
                    color: "#f2f4f3",
                  }}
                />
                <Bar
                  dataKey="plannedMinutesChart"
                  name="Tervezett idő"
                  fill="#737977"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="actualMinutesChart"
                  name="Tényleges idő"
                  fill="var(--accent)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
            <p>
              <b>X tengely:</b> hét kezdete · <b>Y tengely:</b> edzésidő
              (perc). A szürke oszlop a terv, az akcentusszínű a Garminból
              érkezett tényadat. A hiányzó oszlop nem nulla értéket, hanem
              hiányzó terv- vagy tényadatot jelent.
            </p>
          </div>
          <article className="plan-history-insight">
            <Sparkles size={20} aria-hidden="true" />
            <div>
              <h3>Mit tanulhatunk az eddigi hetekből?</h3>
              <p>{history.insight}</p>
            </div>
          </article>
          <div className="plan-history-table-wrap">
            <table className="plan-history-table">
              <thead>
                <tr>
                  <th>HÉT</th>
                  <th>TERV / TÉNY IDŐ</th>
                  <th>TERVKÖVETÉS</th>
                  <th>ÁTLAGOS RPE</th>
                  <th>TERVMÓDOSÍTÁS</th>
                  <th>ÉRTELMEZÉS</th>
                </tr>
              </thead>
              <tbody>
                {[...history.dataWeeks].reverse().map((week) => (
                  <tr key={week.from}>
                    <td>{week.periodLabel}</td>
                    <td>
                      {week.weekPlans.length
                        ? formatMinutes(week.plannedMinutes)
                        : "Nincs terv"}{" "}
                      /{" "}
                      {week.weekActivities.length
                        ? formatMinutes(week.actualMinutes)
                        : "Nincs tényadat"}
                    </td>
                    <td>
                      {week.adherence === null ? "Nincs terv" : `${week.adherence}%`}
                    </td>
                    <td>
                      {week.averageRpe === null
                        ? "Nincs adat"
                        : `${week.averageRpe.toLocaleString("hu-HU", { maximumFractionDigits: 1 })} / 10`}
                    </td>
                    <td>
                      {week.adjustment === null
                        ? "Nincs rögzített adaptáció"
                        : `${week.adjustment > 0 ? "+" : ""}${week.adjustment.toLocaleString("hu-HU", { maximumFractionDigits: 1 })}% volumen`}
                    </td>
                    <td>
                      <span className={`plan-history-status ${week.statusTone}`}>
                        {week.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="plan-history-note">
            Az összegzés a saját előzményeidben látható együttjárást mutatja,
            nem bizonyít ok-okozati kapcsolatot és nem helyettesít szakmai vagy
            orvosi döntést. A hiányzó adatokat nem tekintjük nullának.
          </p>
        </>
      )}
    </section>
  );
}
export function WeeklyClosureCard({
  plans = [],
  activities = [],
  feedback = {},
  loading = false,
  onNavigate,
}) {
  const today = budapestToday(),
    closure = useMemo(
      () => buildWeeklyClosure(plans, activities, feedback, today),
      [plans, activities, feedback, today],
    );
  if (loading) {
    return (
      <section className="weekly-closure card" aria-live="polite">
        <span className="eyebrow">HETI LEZÁRÁS</span>
        <p className="weekly-closure-empty">A heti adatok betöltése folyamatban…</p>
      </section>
    );
  }
  if (!closure) {
    return (
      <section className="weekly-closure card">
        <span className="eyebrow">HETI LEZÁRÁS</span>
        <h2>Még nincs értékelhető hét</h2>
        <p className="weekly-closure-empty">
          Az első edzés vagy heti terv után itt jelenik meg a teljesítés,
          a visszajelzés lefedettsége és a következő heti döntés.
        </p>
        <button className="weekly-closure-action" onClick={() => onNavigate("Naptár")}>
          ELSŐ HÉT MEGTERVEZÉSE <ChevronRight size={16} />
        </button>
      </section>
    );
  }
  return (
    <section className="weekly-closure card" aria-labelledby="weekly-closure-title">
      <header className="weekly-closure-head">
        <div>
          <span className="eyebrow">
            HETI LEZÁRÁS · {closure.isCurrent ? "FUTÓ HÉT" : "LEZÁRT HÉT"}
          </span>
          <h2 id="weekly-closure-title">{closure.periodLabel}</h2>
          <p>
            A legutóbbi adatokból összefoglaljuk, mi történt és mi legyen a
            következő, biztonságosan indokolható lépés.
          </p>
        </div>
        <button
          className="weekly-closure-action"
          onClick={() => onNavigate("Cél", { openAdaptive: true })}
        >
          KÖVETKEZŐ HÉT TERVEZÉSE <ChevronRight size={16} />
        </button>
      </header>
      <div className="weekly-closure-metrics" aria-label="A hét fő mutatói">
        <span>
          <strong>{closure.weekActivities.length}</strong>
          <b>EDZÉS</b>
          <small>Ennyi külön Garmin-aktivitás került a hétbe.</small>
        </span>
        <span>
          <strong>{formatMinutes(closure.actualMinutes)}</strong>
          <b>EDZÉSIDŐ</b>
          <small>
            {closure.plannedMinutes
              ? `${formatMinutes(closure.plannedMinutes)} volt betervezve.`
              : "Nem volt előre rögzített heti időterv."}
          </small>
        </span>
        <span>
          <strong>
            {closure.adherence === null ? "—" : `${closure.adherence}%`}
          </strong>
          <b>TERVKÖVETÉS</b>
          <small>
            {closure.weekPlans.length
              ? `${closure.completed} / ${closure.weekPlans.length} tervhez találtunk edzést.`
              : "Terv nélkül ez az arány nem számítható."}
          </small>
        </span>
        <span>
          <strong>
            {closure.feedbackCount} / {closure.weekActivities.length}
          </strong>
          <b>VISSZAJELZÉS</b>
          <small>
            {closure.averageRpe === null
              ? "Nincs rögzített RPE; ez nem nulla terhelést jelent."
              : `Átlagos rögzített RPE: ${closure.averageRpe.toLocaleString("hu-HU", { maximumFractionDigits: 1 })} / 10.`}
          </small>
        </span>
      </div>
      <div className="weekly-closure-insights">
        <article>
          <span>1</span>
          <div>
            <h3>Mi teljesült?</h3>
            <p>{closure.completedText}</p>
          </div>
        </article>
        <article>
          <span>2</span>
          <div>
            <h3>Mit jelez?</h3>
            <p>{closure.signalText}</p>
          </div>
        </article>
        <article className="next-step">
          <span>3</span>
          <div>
            <h3>Következő döntés</h3>
            <p>{closure.nextDecision}</p>
          </div>
        </article>
      </div>
      <p className="weekly-closure-note">
        Ez döntéstámogatás, nem orvosi minősítés. A hiányzó tervet vagy
        visszajelzést a rendszer nem kezeli nulla értékként.
      </p>
    </section>
  );
}
export function PlanningFlow({ active, profile, plans = [], feedback = {}, onNavigate }) {
  const today = budapestToday(),
    nextPlan = [...plans]
      .filter((plan) => plan.date >= today)
      .sort((a, b) => a.date.localeCompare(b.date))[0],
    steps = [
      {
        id: "Cél",
        Icon: Target,
        label: "1. Cél",
        detail: profile.eventName || profile.goal,
      },
      {
        id: "Naptár",
        Icon: CalendarDays,
        label: "2. Terv",
        detail: nextPlan
          ? `Következő: ${new Date(`${nextPlan.date}T12:00:00`).toLocaleDateString("hu-HU", { month: "short", day: "numeric" })}`
          : "Még nincs következő edzés",
        context: nextPlan ? { calendarDate: nextPlan.date } : {},
      },
      {
        id: "Napló",
        Icon: ClipboardList,
        label: "3. Visszajelzés",
        detail: `${Object.keys(feedback || {}).length} értékelt edzés`,
      },
    ];
  return (
    <nav
      className="planning-flow card"
      aria-label="Cél, edzésterv és visszajelzés folyamata"
    >
      <div className="planning-flow-intro">
        <span className="eyebrow">TERVEZÉSI FOLYAMAT</span>
        <p>A célból heti terv, a teljesítésből pedig következő döntés lesz.</p>
      </div>
      <div className="planning-flow-steps">
        {steps.map(({ id, Icon, label, detail, context }) => (
          <button
            type="button"
            key={id}
            className={active === id ? "active" : ""}
            aria-current={active === id ? "step" : undefined}
            onClick={() => onNavigate(id, context || {})}
          >
            <Icon size={19} aria-hidden="true" />
            <span>
              <b>{label}</b>
              <small>{detail}</small>
            </span>
            {id !== "Napló" && <ChevronRight size={16} aria-hidden="true" />}
          </button>
        ))}
      </div>
    </nav>
  );
}
