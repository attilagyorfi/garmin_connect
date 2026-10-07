import { useState } from "react";
import { Activity, ChevronLeft, ChevronRight, ClipboardList, Pencil, Plus } from "lucide-react";
import { PageHeader } from "../components/PageHeader.jsx";
import { BatchMoveEditor } from "../components/calendar/BatchMoveEditor.jsx";
import { PlanEditor } from "../components/calendar/PlanEditor.jsx";
import { WeeklyTemplateEditor } from "../components/calendar/WeeklyTemplateEditor.jsx";
import { PlanningFlow } from "../components/planning/PlanOutcome.jsx";
import { useDashboardData } from "../lib/api.js";
import { dayCodes, isoDate } from "../lib/dates.js";
import { budapestToday } from "../lib/overviewData.js";
import { evaluatePlanSet, summarizePlanWeek } from "../lib/planOutcomes.js";
import { buildPersonalWeek, emptyPlan } from "../lib/planning.js";

// A day can hold several plans and several Garmin activities; each activity satisfies at most one plan.
export function PersistentCalendarPage({
  profile,
  cloudState,
  onCloudPatch,
  initialDate,
  onNavigate,
}) {
  const data = useDashboardData(),
    activities = data?.sessions || [],
    today = budapestToday(),
    anchorDate = initialDate || today,
    anchor = new Date(`${anchorDate}T12:00:00`),
    [month, setMonth] = useState(
      () => new Date(anchor.getFullYear(), anchor.getMonth(), 1),
    ),
    [selected, setSelected] = useState(() => isoDate(anchor)),
    [editor, setEditor] = useState(null),
    [templateEditor, setTemplateEditor] = useState(false),
    [batchEditor, setBatchEditor] = useState(false),
    plans = cloudState?.plans || [],
    planned = plans.reduce((map, item) => map.set(item.date, [...(map.get(item.date) || []), item]), new Map()),
    actual = activities.reduce((map, item) => {
      const normalized = {...item,title:item.name,duration:item.durationMin,status:"done"};
      return map.set(item.date, [...(map.get(item.date) || []), normalized]);
    }, new Map());
  const first = new Date(month.getFullYear(), month.getMonth(), 1),
    gridStart = new Date(first);
  gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const cells = Array.from({ length: 42 }, (_, index) => {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + index);
      const key = isoDate(date),
        items = [...(actual.get(key) || []), ...(planned.get(key) || [])];
      return { date, key, items, item:items[0], current: date.getMonth() === month.getMonth() };
    }),
    selectedPlans = planned.get(selected) || [],
    selectedActuals = actual.get(selected) || [],
    selectedItems = [...selectedActuals, ...selectedPlans],
    selectedDate = new Date(`${selected}T12:00:00`),
    monthLabel = month.toLocaleDateString("hu-HU", {
      year: "numeric",
      month: "long",
    }),
    shift = (value) =>
      setMonth(
        (current) =>
          new Date(current.getFullYear(), current.getMonth() + value, 1),
      ),
    save = (plan) => {
      onCloudPatch({ plan });
      setSelected(plan.date);
      setEditor(null);
    },
    remove = (id) => {
      onCloudPatch({ deletePlan: id });
      setEditor(null);
    },
    template = buildPersonalWeek(profile, data),
    saveTemplate = (items) => {
      onCloudPatch({ plans: items });
      setTemplateEditor(false);
      if (items[0]) setSelected(items[0].date);
    },
    saveBatch = (items) => {
      onCloudPatch({ plans: items });
      setBatchEditor(false);
      if (items[0]) setSelected(items[0].date);
    },
    selectedPlanResults = evaluatePlanSet(selectedPlans, activities, today),
    weekSummary = summarizePlanWeek(
      plans,
      activities,
      selected,
      cloudState?.feedback || {},
    );
  return (
    <>
      <PageHeader eyebrow="SZEMÉLYES HETI TERV" title="Terv és tény">
        <div className="calendar-actions">
          <button aria-label="Előző hónap" onClick={() => shift(-1)}>
            <ChevronLeft size={14} />
          </button>
          <b>{monthLabel}</b>
          <button aria-label="Következő hónap" onClick={() => shift(1)}>
            <ChevronRight size={14} />
          </button>
          <button
            className="calendar-new"
            onClick={() => setEditor(emptyPlan(selected))}
          >
            <Plus size={15} /> ÚJ EDZÉS
          </button>
        </div>
      </PageHeader>
      <PlanningFlow
        active="Naptár"
        profile={profile}
        plans={plans}
        feedback={cloudState?.feedback || {}}
        onNavigate={onNavigate}
      />
      <section
        className="calendar-week-summary card"
        aria-label="A kiválasztott hét terv és tény összesítése"
      >
        <div>
          <span className="eyebrow">KIVÁLASZTOTT HÉT</span>
          <b>
            {new Date(`${weekSummary.from}T12:00:00`).toLocaleDateString(
              "hu-HU",
              { month: "short", day: "numeric" },
            )}{" "}
            –{" "}
            {new Date(`${weekSummary.to}T12:00:00`).toLocaleDateString(
              "hu-HU",
              { month: "short", day: "numeric" },
            )}
          </b>
        </div>
        <span>
          <strong>{weekSummary.weekPlans.length}</strong>
          <small>TERVEZETT EDZÉS</small>
        </span>
        <span>
          <strong>{weekSummary.completed}</strong>
          <small>TERVHEZ PÁROSÍTVA</small>
        </span>
        <span>
          <strong>
            {/* No plan is "nincs terv", not 0; actual time counts every Garmin activity of the week, matched or not. */}
            {weekSummary.weekPlans.length ? `${weekSummary.plannedMinutes}p` : "nincs terv"} /{" "}
            {weekSummary.weekActivities.length
              ? `${weekSummary.weekActivities.reduce((sum, item) => sum + Number(item.durationMin || 0), 0)}p`
              : "nincs tény"}
          </strong>
          <small>TERV / TÉNY IDŐ</small>
        </span>
        <span>
          <strong>
            {weekSummary.adherence == null ? "—" : `${weekSummary.adherence}%`}
          </strong>
          <small>TERVKÖVETÉS</small>
        </span>
        <span>
          <strong>
            {weekSummary.feedbackCount} / {weekSummary.weekActivities.length}
          </strong>
          <small>VISSZAJELZÉS</small>
        </span>
      </section>
      <div className="calendar-toolbar">
        <div className="calendar-legend">
          <span>
            <i className="planned" />
            TERVEZETT
          </span>
          <span>
            <i className="done" />
            TELJESÍTETT
          </span>
          <span>
            <i className="extra" />
            GARMIN ELŐZMÉNY
          </span>
        </div>
        <div className="calendar-toolbar-actions">
          <button
            disabled={plans.length < 2}
            onClick={() => setBatchEditor(true)}
          >
            TÖBB EDZÉS MOZGATÁSA
          </button>
          <button onClick={() => setTemplateEditor(true)}>
            HETI SABLON SZEMÉLYRE SZABÁSA
          </button>
        </div>
      </div>
      <section className="calendar card">
        <div className="weekdays">
          {[
            "HÉTFŐ",
            "KEDD",
            "SZERDA",
            "CSÜTÖRTÖK",
            "PÉNTEK",
            "SZOMBAT",
            "VASÁRNAP",
          ].map((day) => (
            <b key={day}>{day}</b>
          ))}
        </div>
        <div className="calendar-grid">
          {cells.map((cell) => (
            <button
              key={cell.key}
              className={`${cell.key === selected ? "selected" : ""} ${!cell.current ? "outside" : ""}`}
              onClick={() => setSelected(cell.key)}
            >
              <span>{cell.date.getDate()}</span>
              {cell.item && (
                <div className={cell.item.status}>
                  <Activity size={13} />
                  <b>{cell.item.type}</b>
                  <small>
                    {cell.items.length > 1 ? `${cell.items.length} edzés · ${cell.items.reduce((sum,item)=>sum+Number(item.duration||0),0)}p` : `${cell.item.title} · ${cell.item.duration}p`}
                  </small>
                </div>
              )}
            </button>
          ))}
        </div>
      </section>
      <div className="calendar-detail card">
        <div>
          <span className="eyebrow">KIVÁLASZTOTT NAP</span>
          <h2>
            {selectedDate.toLocaleDateString("hu-HU", {
              month: "long",
              day: "numeric",
            })}
          </h2>
        </div>
        <div>
          <div className="selected-day-sessions">
            {selectedItems.length
              ? <>
                  {selectedPlans.map((plan) => {
                    const result = selectedPlanResults.get(plan.id);
                    return (
                      <article className="selected-plan" key={plan.id}>
                        <div>
                          <span>TERV</span>
                          <b>{plan.title}</b>
                          <small>
                            {plan.duration} perc · {plan.intensity} · RPE {plan.rpe}/10
                          </small>
                        </div>
                        <div
                          className={`plan-comparison ${result.status.replaceAll(" ", "-")}`}
                        >
                          <b>{result.status.toUpperCase()}</b>
                          {result.activity && (
                            <span>
                              {result.method} párosítás · tény{" "}
                              {result.activity.durationMin} perc · eltérés{" "}
                              {result.difference > 0 ? "+" : ""}
                              {result.difference} perc
                            </span>
                          )}
                        </div>
                        <button onClick={() => setEditor(plan)}>
                          <Pencil size={14} /> SZERKESZTÉS
                        </button>
                      </article>
                    );
                  })}
                  {selectedActuals.map((activity) => (
                    <article className="selected-actual" key={activity.id}>
                      <div>
                        <span>GARMIN</span>
                        <b>{activity.title}</b>
                        <small>
                          {activity.duration} perc · terhelés:{" "}
                          {activity.load ?? "nem ismert"}
                        </small>
                      </div>
                      <button
                        onClick={() =>
                          onNavigate("Napló", {
                            journalActivityId: activity.id,
                          })
                        }
                      >
                        <ClipboardList size={14} /> NAPLÓ MEGNYITÁSA
                      </button>
                    </article>
                  ))}
                </>
              : selectedDate.getDay() === 0 ||
                  dayCodes[selectedDate.getDay()] === profile.restDay
                ? "Tervezett pihenőnap."
                : "Nincs edzés erre a napra."}
          </div>
        </div>
        <div className="calendar-detail-actions">
          <button
            className="primary"
            onClick={() => setEditor(emptyPlan(selected))}
          >
            <Plus size={14} /> EDZÉS HOZZÁADÁSA
          </button>
        </div>
      </div>
      {editor && (
        <PlanEditor
          value={editor}
          activities={activities}
          onSave={save}
          onDelete={remove}
          onClose={() => setEditor(null)}
        />
      )}{" "}
      {templateEditor && (
        <WeeklyTemplateEditor
          items={template}
          onSave={saveTemplate}
          onClose={() => setTemplateEditor(false)}
        />
      )}{" "}
      {batchEditor && (
        <BatchMoveEditor
          plans={plans}
          onSave={saveBatch}
          onClose={() => setBatchEditor(false)}
        />
      )}
    </>
  );
}

