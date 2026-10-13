import test from "node:test";
import assert from "node:assert/strict";
import { EVENTS, buildEventPlan, currentRunning, inferEventType, paceZones, parseRaceTime, formatDuration } from "../src/lib/eventTemplates.js";

const TODAY = "2026-10-13"; // Tuesday
const profile = { experience: "középhaladó", eventName: "Budapest Maraton", eventDate: "2027-02-21", trainingDays: ["H", "K", "Sze", "Cs", "P", "Szo", "V"], restDay: "H", strengthRatio: 20 };
const runs = Array.from({ length: 16 }, (_, index) => {
  const date = new Date(`${TODAY}T12:00:00`); date.setDate(date.getDate() - index * 1.7);
  return { type: "Futás", date: date.toISOString().slice(0, 10), distanceKm: index % 4 === 0 ? 16 : 8, durationMin: index % 4 === 0 ? 100 : 46 };
});
const data = { today: TODAY, sessions: runs };

test("race time parsing and formatting", () => {
  assert.equal(parseRaceTime("50:00"), 3000);
  assert.equal(parseRaceTime("1:45:30"), 6330);
  assert.equal(parseRaceTime("abc"), null);
  assert.equal(parseRaceTime("3:00"), null); // under 10 minutes is not a plausible race of these distances
  assert.equal(formatDuration(13800), "3:50:00");
});

test("Riegel prediction from a 50-minute 10 km", () => {
  const { predictions, zones } = paceZones("10k", 3000);
  const marathon = predictions.marathon;
  assert.ok(marathon > 3 * 3600 + 45 * 60 && marathon < 3 * 3600 + 55 * 60, `marathon ${formatDuration(marathon)}`);
  const threshold = zones.find(zone => zone.key === "threshold");
  const tenKPace = 300; // 5:00/km
  assert.ok(threshold.from > tenKPace && threshold.from < tenKPace * 1.08, "threshold just slower than 10 km pace");
  const easy = zones.find(zone => zone.key === "easy");
  assert.ok(easy.from > predictions.marathon / EVENTS.marathon.km, "easy is slower than marathon pace");
});

test("event type is inferred from the profile", () => {
  assert.equal(inferEventType({ eventName: "Wizz Air Félmaraton" }), "half");
  assert.equal(inferEventType({ eventName: "Budapest Maraton" }), "marathon");
  assert.equal(inferEventType({ eventType: "10k", eventName: "Maraton" }), "10k");
  assert.equal(inferEventType({ eventName: "Tavaszi túra" }), null);
});

test("recent running volume ignores other sports and missing distances", () => {
  const current = currentRunning([...runs, { type: "Erő", date: TODAY, durationMin: 60 }, { type: "Futás", date: TODAY, distanceKm: null }], TODAY);
  assert.ok(current.weeklyKm >= 30 && current.weeklyKm <= 45, `weekly ${current.weeklyKm}`);
  assert.equal(current.longestKm, 16);
  assert.deepEqual(currentRunning([], TODAY), { weeklyKm: null, longestKm: null, easyPace: null, runs: 0 });
});

test("marathon plan: dates, progression, taper and long-run cap", () => {
  const plan = buildEventPlan({ profile, data, eventType: "marathon", referenceKey: "10k", referenceSeconds: 3000, today: TODAY });
  const { weeks, summary } = plan;
  assert.ok(weeks.length >= EVENTS.marathon.weeks.min && weeks.length <= EVENTS.marathon.weeks.max);
  // the race is on the event date, in the last week
  const race = weeks.at(-1).sessions.find(item => item.title.startsWith("Verseny"));
  assert.equal(race.date, "2027-02-21");
  // conservative progression between consecutive build weeks, and never >30% over two weeks
  // full weeks grow at most ~10% over the previous full week (a cut-back week is a dip, not a new base)
  const full = weeks.filter(week => week.phase !== "Taper" && week.phase !== "Tehermentesítés");
  for (let index = 1; index < full.length; index += 1) assert.ok(full[index].km <= full[index - 1].km * 1.1 + 1.5, `${full[index - 1].km} -> ${full[index].km}`);
  assert.ok(weeks.some(week => week.phase === "Tehermentesítés"), "cut-back weeks are planned");
  for (let index = 2; index < full.length; index += 1) assert.ok(full[index].km <= full[index - 2].km * 1.3 + 1.5, `two-week jump: ${full[index - 2].km} -> ${full[index].km}`);
  // the week after a cut-back rejoins the previous level instead of adding on top of it
  weeks.forEach((week, index) => { if (week.phase === "Tehermentesítés" && weeks[index + 1]?.phase !== "Taper" && weeks[index - 1]) assert.ok(weeks[index + 1].km <= weeks[index - 1].km + 1.5); });
  // taper: three weeks, last week 41–60% below the peak, intensity kept (a quality session remains)
  const taper = weeks.filter(week => week.phase === "Taper");
  assert.equal(taper.length, 3);
  const lastWeekTraining = taper.at(-1).trainingKm;
  assert.equal(taper.at(-1).raceKm, EVENTS.marathon.km);
  assert.ok(summary.peakKm <= EVENTS.marathon.peakKm["középhaladó"] + 1.5, "peak excludes the race distance");
  assert.ok(lastWeekTraining / summary.peakKm <= 0.6, "race-week training volume is cut by at least 40%");
  assert.ok(taper.every(week => week.sessions.some(item => item.intensity === "közepes–magas" || item.title.startsWith("Verseny"))));
  // long run capped, rest day respected, mostly easy running
  assert.ok(summary.longestRunKm <= EVENTS.marathon.longCap);
  for (const week of weeks) {
    for (const session of week.sessions) assert.notEqual(new Date(`${session.date}T12:00:00`).getDay(), 1, "no session on the rest day (Monday)");
    if (week.phase !== "Taper") assert.ok(week.easyShare >= 70, `week ${week.index} easy share ${week.easyShare}%`);
  }
  assert.ok(plan.paces && summary.predictedSeconds > 0);
});

test("short preparation is flagged, missing data is reported, not invented", () => {
  const plan = buildEventPlan({ profile: { ...profile, eventDate: "2026-11-15" }, data: { today: TODAY, sessions: [] }, eventType: "marathon", today: TODAY });
  assert.ok(plan.weeks.length < EVENTS.marathon.weeks.min);
  assert.ok(plan.warnings.some(text => text.includes("rövidített")));
  assert.ok(plan.warnings.some(text => text.includes("nincs Garmin-futásadat")));
  assert.ok(plan.warnings.some(text => text.includes("tempózónákat")));
  assert.equal(plan.paces, null);
});

test("far-away event starts the targeted block later; strength stays in a hybrid week", () => {
  const plan = buildEventPlan({ profile: { ...profile, eventType: "10k", eventDate: "2027-09-01" }, data, eventType: "10k", today: TODAY });
  assert.equal(plan.weeks.length, EVENTS["10k"].weeks.max);
  assert.ok(plan.weeks[0].weekStart > "2027-06-01");
  assert.ok(plan.warnings.some(text => text.includes("addig tartsd")));
  assert.ok(plan.weeks[1].sessions.some(item => item.type === "Erő"));
});

test("a too-low starting volume gets an explicit recommendation instead of a pretend marathon plan", () => {
  const few = [{ type: "Futás", date: TODAY, distanceKm: 5, durationMin: 32 }, { type: "Futás", date: "2026-10-08", distanceKm: 6, durationMin: 38 }];
  const plan = buildEventPlan({ profile, data: { today: TODAY, sessions: few }, eventType: "marathon", today: TODAY });
  assert.match(plan.warnings[0], /félmaratont/);
  assert.equal(plan.summary.distanceReady, false);
  // the first week starts from what the athlete actually runs, not from fixed session minimums
  assert.ok(plan.weeks.every(week => week.easyShare == null || week.easyShare >= 70), "low-volume weeks stay mostly easy");
  assert.ok(plan.weeks[0].trainingKm <= plan.summary.startKm * 1.25 + 2, `first week ${plan.weeks[0].trainingKm} km vs start ${plan.summary.startKm} km`);
  assert.ok(plan.summary.longestRunKm < 24);
});
