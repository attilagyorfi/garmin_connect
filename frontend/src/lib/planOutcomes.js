import { isoDate } from "./dates.js";
import { formatMinutes } from "./periods.js";
import { activityMatchesType, evaluatePlan } from "./planning.js";

// Plan vs. Garmin activity: one activity satisfies at most one plan (manual links first),
// weekly closure text and the multi-week outcome history. A week without plans is "no plan",
// never a zero-percent adherence.
export function evaluatePlanSet(plans, activities, today) {
  const usedActivityIds = new Set(),
    results = new Map();
  [...(plans || [])]
    .sort((left, right) =>
      Number(Boolean(right.matchedActivityId)) -
      Number(Boolean(left.matchedActivityId)),
    )
    .forEach((plan) => {
      const manual =
          plan.matchedActivityId &&
          activities.find(
            (item) =>
              String(item.id) === String(plan.matchedActivityId) &&
              !usedActivityIds.has(String(item.id)),
          ),
        automatic = [...activities]
          .filter(
            (item) =>
              !usedActivityIds.has(String(item.id)) &&
              item.date === plan.date &&
              activityMatchesType(plan, item),
          )
          .sort(
            (left, right) =>
              Math.abs(Number(left.durationMin || 0) - Number(plan.duration || 0)) -
              Math.abs(Number(right.durationMin || 0) - Number(plan.duration || 0)),
          )[0],
        activity = manual || automatic;
      if (!activity) {
        results.set(plan.id, evaluatePlan(plan, [], today));
        return;
      }
      usedActivityIds.add(String(activity.id));
      results.set(plan.id, {
        ...evaluatePlan(
          { ...plan, matchedActivityId: activity.id },
          [activity],
          today,
        ),
        method: manual ? "kézi" : "automatikus",
      });
    });
  return results;
}
export function buildActivityPlanLinks(plans, activities, today) {
  const links = new Map(),
    evaluations = evaluatePlanSet(plans, activities, today);
  (plans || []).forEach((plan) => {
    const comparison = evaluations.get(plan.id);
    if (comparison?.activity) {
      links.set(String(comparison.activity.id), { plan, comparison });
    }
  });
  return links;
}
export function summarizePlanWeek(plans, activities, referenceDate, feedback = {}) {
  const reference = new Date(`${referenceDate}T12:00:00`),
    monday = new Date(reference),
    dayOffset = (reference.getDay() + 6) % 7;
  monday.setDate(reference.getDate() - dayOffset);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const from = isoDate(monday),
    to = isoDate(sunday),
    weekPlans = (plans || []).filter(
      (plan) => plan.date >= from && plan.date <= to,
    ),
    weekActivities = (activities || []).filter(
      (activity) => activity.date >= from && activity.date <= to,
    ),
    evaluated = [...evaluatePlanSet(weekPlans, activities, referenceDate).values()],
    completed = evaluated.filter((item) => item.activity).length,
    plannedMinutes = weekPlans.reduce(
      (sum, plan) => sum + Number(plan.duration || 0),
      0,
    ),
    actualMinutes = evaluated.reduce(
      (sum, item) => sum + Number(item.activity?.durationMin || 0),
      0,
    ),
    feedbackCount = weekActivities.filter((item) => feedback[item.id]).length;
  return {
    from,
    to,
    weekPlans,
    weekActivities,
    completed,
    plannedMinutes,
    actualMinutes,
    feedbackCount,
    adherence: weekPlans.length
      ? Math.round((completed / weekPlans.length) * 100)
      : null,
  };
}
export function buildWeeklyClosure(plans, activities, feedback, today) {
  const shiftDate = (date, days) => {
      const shifted = new Date(`${date}T12:00:00`);
      shifted.setDate(shifted.getDate() + days);
      return isoDate(shifted);
    },
    formatDay = (date) =>
      new Date(`${date}T12:00:00`).toLocaleDateString("hu-HU", {
        month: "short",
        day: "numeric",
      });
  let week = null;
  for (let offset = 0; offset < 16; offset += 1) {
    const candidate = summarizePlanWeek(
      plans,
      activities,
      shiftDate(today, offset * -7),
      feedback,
    );
    if (candidate.weekPlans.length || candidate.weekActivities.length) {
      week = candidate;
      break;
    }
  }
  if (!week) return null;

  const evaluations = [
      ...evaluatePlanSet(week.weekPlans, week.weekActivities, today).values(),
    ],
    matchedActivityIds = new Set(
      evaluations
        .filter((item) => item.activity)
        .map((item) => String(item.activity.id)),
    ),
    extraActivities = week.weekActivities.filter(
      (item) => !matchedActivityIds.has(String(item.id)),
    ),
    missed = evaluations.filter(
      (item) => !item.activity && item.status === "elmaradt",
    ).length,
    actualMinutes = week.weekActivities.reduce(
      (sum, item) => sum + Number(item.durationMin || 0),
      0,
    ),
    rpeValues = week.weekActivities
      .map((item) => Number(feedback?.[item.id]?.rpe))
      .filter((value) => Number.isFinite(value) && value > 0),
    averageRpe = rpeValues.length
      ? rpeValues.reduce((sum, value) => sum + value, 0) / rpeValues.length
      : null,
    feedbackCoverage = week.weekActivities.length
      ? Math.round((week.feedbackCount / week.weekActivities.length) * 100)
      : null,
    durationRatio = week.plannedMinutes
      ? actualMinutes / week.plannedMinutes
      : null,
    isCurrent = week.from <= today && week.to >= today,
    periodLabel = `${formatDay(week.from)} – ${formatDay(week.to)}`;

  let completedText;
  if (!week.weekPlans.length) {
    completedText = `${week.weekActivities.length} edzés került a Naplóba, összesen ${formatMinutes(actualMinutes)}. Előzetes terv nélkül a tervkövetést nem tudjuk kiszámolni.`;
  } else {
    completedText = `${week.completed} / ${week.weekPlans.length} tervezett edzéshez találtunk elvégzett edzést. ${missed ? `${missed} edzés elmaradt.` : "Elmaradt edzés nincs."}${extraActivities.length ? ` Emellett ${extraActivities.length} nem tervezett edzésed is volt.` : ""}`;
  }

  let signalText;
  if (!week.weekActivities.length) {
    signalText = "Ezen a héten még nincs Garmin-edzés, ezért a terv tényleges terhelését nem tudjuk értékelni.";
  } else if (feedbackCoverage === 0) {
    signalText = "Az edzésadatok megvannak, de saját visszajelzésed még nincs. A hiányzó RPE (edzésérzet) nem nulla terhelés, hanem kevésbé biztos értékelés.";
  } else if (feedbackCoverage < 60) {
    signalText = `Az edzések ${feedbackCoverage}%-ához van saját visszajelzésed. Ez már támpont, de még csak részben látszik, mennyire volt nehéz a heted.`;
  } else if (averageRpe >= 8) {
    signalText = `A rögzített RPE-d (edzésérzet) átlaga ${averageRpe.toLocaleString("hu-HU", { maximumFractionDigits: 1 })} / 10, vagyis többnyire nehéznek érezted a hetet. A következő emelés előtt érdemes ezen a szinten maradnod.`;
  } else {
    signalText = `Az edzések ${feedbackCoverage}%-ához adtál visszajelzést, az átlagos RPE-d (edzésérzet) ${averageRpe.toLocaleString("hu-HU", { maximumFractionDigits: 1 })} / 10. Ez használható alap a következő hét finomításához.`;
  }

  let nextDecision;
  if (!week.weekPlans.length) {
    nextDecision = "Tervezd meg előre legalább a következő hét fő edzéseit a Naptárban. Így nemcsak azt látjuk, mit végeztél el, hanem azt is, mennyire tértél el a tervtől.";
  } else if (feedbackCoverage === null || feedbackCoverage < 50) {
    nextDecision = "A következő héten minden fő edzés után add meg az RPE-t, vagyis hogy mennyire érezted nehéznek. Enélkül, csak a Garmin-adatok alapján nem indokolt emelni vagy csökkenteni a terhelést.";
  } else if (week.adherence < 70) {
    nextDecision = "Ne sűrítsd be automatikusan az elmaradt edzéseket. Előbb egyszerűsítsd a következő hetet: legyen benne kevesebb, biztosan teljesíthető fő edzés.";
  } else if ((durationRatio && durationRatio > 1.2) || averageRpe >= 8) {
    nextDecision = "Tartsd vagy kicsit csökkentsd a következő hét edzésmennyiségét. Új terhelést csak akkor adj hozzá, ha a regenerációd jelei is engedik.";
  } else {
    nextDecision = "A heti felépítés tartható. A következő héten csak egy dolgon változtass, és az edzésidőt legfeljebb kis lépésben emeld.";
  }

  return {
    ...week,
    actualMinutes,
    averageRpe,
    feedbackCoverage,
    extraCount: extraActivities.length,
    missed,
    isCurrent,
    periodLabel,
    completedText,
    signalText,
    nextDecision,
  };
}
export function buildPlanOutcomeHistory(
  plans,
  activities,
  feedback,
  today,
  weekCount = 8,
) {
  const reference = new Date(`${today}T12:00:00`),
    currentMonday = new Date(reference),
    currentDayOffset = (reference.getDay() + 6) % 7;
  currentMonday.setDate(reference.getDate() - currentDayOffset);
  const formatDay = (date) =>
      new Date(`${date}T12:00:00`).toLocaleDateString("hu-HU", {
        month: "short",
        day: "numeric",
      }),
    weeks = Array.from({ length: weekCount }, (_, index) => {
      const monday = new Date(currentMonday);
      monday.setDate(currentMonday.getDate() - (weekCount - 1 - index) * 7);
      const summary = summarizePlanWeek(
          plans,
          activities,
          isoDate(monday),
          feedback,
        ),
        actualMinutes = summary.weekActivities.reduce(
          (sum, item) => sum + Number(item.durationMin || 0),
          0,
        ),
        rpeValues = summary.weekActivities
          .map((item) => Number(feedback?.[item.id]?.rpe))
          .filter((value) => Number.isFinite(value) && value > 0),
        averageRpe = rpeValues.length
          ? rpeValues.reduce((sum, value) => sum + value, 0) /
            rpeValues.length
          : null,
        feedbackCoverage = summary.weekActivities.length
          ? Math.round(
              (summary.feedbackCount / summary.weekActivities.length) * 100,
            )
          : null,
        durationRatio = summary.plannedMinutes
          ? actualMinutes / summary.plannedMinutes
          : null,
        adjustmentValues = summary.weekPlans
          .map((plan) =>
            String(plan.note || "").match(
              /Heti lezárás alapján:\s*([+-]?\d+(?:[.,]\d+)?)%/i,
            ),
          )
          .filter(Boolean)
          .map((match) => Number(match[1].replace(",", ".")))
          .filter(Number.isFinite),
        adjustment = adjustmentValues.length
          ? adjustmentValues.reduce((sum, value) => sum + value, 0) /
            adjustmentValues.length
          : null,
        isCurrent = summary.from <= today && summary.to >= today,
        hasData = Boolean(
          summary.weekPlans.length || summary.weekActivities.length,
        );

      let status = "Nincs adat",
        statusTone = "neutral";
      if (isCurrent && hasData) {
        status = "Folyamatban";
        statusTone = "current";
      } else if (!summary.weekPlans.length && summary.weekActivities.length) {
        status = "Terv nélkül";
        statusTone = "neutral";
      } else if (summary.weekPlans.length && !summary.weekActivities.length) {
        status = "Nincs teljesítés";
        statusTone = "risk";
      } else if (feedbackCoverage !== null && feedbackCoverage < 50) {
        status = "Kevés visszajelzés";
        statusTone = "warn";
      } else if (summary.adherence !== null && summary.adherence < 70) {
        status = "Nehezen tartható";
        statusTone = "risk";
      } else if (
        (durationRatio !== null && durationRatio > 1.2) ||
        (averageRpe !== null && averageRpe >= 8)
      ) {
        status = "Megterhelő";
        statusTone = "warn";
      } else if (
        summary.adherence !== null &&
        summary.adherence >= 80 &&
        durationRatio !== null &&
        durationRatio >= 0.8 &&
        durationRatio <= 1.2 &&
        averageRpe !== null &&
        averageRpe <= 7.5
      ) {
        status = "Jól tartható";
        statusTone = "good";
      } else if (hasData) {
        status = "Vegyes eredmény";
        statusTone = "neutral";
      }

      return {
        ...summary,
        actualMinutes,
        plannedMinutesChart: summary.weekPlans.length
          ? summary.plannedMinutes
          : null,
        actualMinutesChart: summary.weekActivities.length
          ? actualMinutes
          : null,
        averageRpe,
        feedbackCoverage,
        durationRatio,
        adjustment,
        isCurrent,
        hasData,
        status,
        statusTone,
        label: formatDay(summary.from),
        periodLabel: `${formatDay(summary.from)} – ${formatDay(summary.to)}`,
      };
    }),
    dataWeeks = weeks.filter((week) => week.hasData),
    comparableWeeks = dataWeeks.filter(
      (week) =>
        !week.isCurrent &&
        week.weekPlans.length > 0 &&
        week.weekActivities.length > 0,
    ),
    plannedTotal = dataWeeks.reduce(
      (sum, week) => sum + week.plannedMinutes,
      0,
    ),
    plannedWeekCount = dataWeeks.filter(
      (week) => week.weekPlans.length > 0,
    ).length,
    actualTotal = dataWeeks.reduce(
      (sum, week) => sum + week.actualMinutes,
      0,
    ),
    averageAdherence = comparableWeeks.length
      ? Math.round(
          comparableWeeks.reduce(
            (sum, week) => sum + Number(week.adherence || 0),
            0,
          ) / comparableWeeks.length,
        )
      : null,
    activityCount = dataWeeks.reduce(
      (sum, week) => sum + week.weekActivities.length,
      0,
    ),
    feedbackCount = dataWeeks.reduce(
      (sum, week) => sum + week.feedbackCount,
      0,
    ),
    feedbackCoverage = activityCount
      ? Math.round((feedbackCount / activityCount) * 100)
      : null,
    sustainableWeeks = comparableWeeks.filter(
      (week) =>
        week.feedbackCoverage >= 50 &&
        week.adherence >= 70 &&
        week.durationRatio >= 0.75 &&
        week.durationRatio <= 1.2 &&
        week.averageRpe !== null &&
        week.averageRpe <= 7.5,
    ),
    bestWeek = [...sustainableWeeks].sort((a, b) => {
      const aDistance = Math.abs(100 - a.adherence),
        bDistance = Math.abs(100 - b.adherence);
      if (aDistance !== bDistance) return aDistance - bDistance;
      return (a.averageRpe || 10) - (b.averageRpe || 10);
    })[0];

  let insight;
  if (comparableWeeks.length < 2) {
    insight =
      "Legalább két lezárt, előre megtervezett hét kell ahhoz, hogy lássuk, mennyire tartható a terved. A mostani hetet még nem vesszük végleges eredménynek.";
  } else if (!bestWeek) {
    insight =
      "Még nincs olyan lezárt hét, ahol egyszerre megfelelő a tervkövetés és az edzésidő, és elég az RPE-visszajelzés (edzésérzet). Előbb értékelj több edzést, aztán csak egy dolgon változtass a tervben.";
  } else {
    const adjustmentText =
      bestWeek.adjustment === null
        ? "rögzített tervmódosítás nélkül"
        : `${bestWeek.adjustment > 0 ? "+" : ""}${bestWeek.adjustment.toLocaleString("hu-HU", { maximumFractionDigits: 1 })}%-os tervmódosítás mellett`;
    insight = `${bestWeek.periodLabel} volt a leginkább tartható heted: ${bestWeek.adherence}% tervkövetés, ${bestWeek.averageRpe.toLocaleString("hu-HU", { maximumFractionDigits: 1 })} / 10 átlagos RPE, ${adjustmentText}. Ez együttjárás a saját előzményeidben, nem bizonyított ok-okozati kapcsolat.`;
  }

  return {
    weeks,
    dataWeeks,
    comparableWeeks,
    plannedTotal,
    plannedWeekCount,
    actualTotal,
    averageAdherence,
    feedbackCoverage,
    insight,
  };
}
