import test from "node:test";
import assert from "node:assert/strict";
import { HIKE_SOURCES, buildHikePlan, currentHiking, hikeTarget, walkingMinutes } from "../src/lib/hikeTemplates.js";

const TODAY = "2026-10-13"; // Tuesday
const hikes = [
  { type: "Túrázás", date: "2026-10-04", durationMin: 240, distanceKm: 14, ascentM: 700 },
  { type: "Túrázás", date: "2026-09-20", durationMin: 200, distanceKm: 12, ascentM: 600 },
  { type: "Túrázás", date: "2026-09-06", durationMin: 150, distanceKm: 9, ascentM: 400 },
];
const week = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];
const dayHike = { eventType: "hike", eventName: "Mátrabérc", eventDate: "2027-01-17", hikeKm: 30, hikeGainM: 1500, experience: "középhaladó", trainingDays: week, restDay: "H" };
const trek = { eventType: "trek", eventName: "Kéktúra-szakasz", eventDate: "2027-02-27", hikeKm: 22, hikeGainM: 900, hikeDays: 5, hikePackKg: 12, trainingDays: ["K", "Sze", "Cs", "Szo", "V"], restDay: "H" };
const hikeSessions = plan => plan.weeks.flatMap(item => item.sessions);
const isLong = item => item.type === "Túrázás" && item.title.startsWith("Hosszú");

test("DIN 33466 walking time: the smaller part counts half", () => {
  assert.equal(walkingMinutes(8, 900, 0), 240); // Alpenverein example: 3 h climbing + 2 h distance → 4 h
  assert.equal(walkingMinutes(4, 300, 500), 150); // 1 h + 1 h vertical, 1 h horizontal → 2.5 h
});

test("profile values outside the allowed range are ignored", () => {
  assert.equal(hikeTarget({ eventType: "marathon" }), null);
  const target = hikeTarget({ eventType: "hike", hikeKm: 200, hikeGainM: 1200, hikeDays: 6, hikePackKg: 40 });
  assert.deepEqual([target.km, target.gainM, target.days, target.packKg], [null, 1200, 1, 5]);
  assert.equal(buildHikePlan({ profile: { ...dayHike, hikeKm: null }, data: { today: TODAY }, today: TODAY }), null);
});

test("recent hiking gives a clamped personal pace factor", () => {
  const current = currentHiking([...hikes, { type: "Futás", date: TODAY, durationMin: 50, distanceKm: 10 }], TODAY);
  assert.equal(current.hikes, 3);
  assert.equal(current.longestMin, 240);
  assert.equal(current.maxGainM, 700);
  assert.ok(current.paceFactor >= 0.7 && current.paceFactor <= 1.4);
  assert.equal(currentHiking([hikes[0]], TODAY).paceFactor, null); // one hike is not enough
});

test("one-day hike: long hike grows ≤10% a week, cut-back every 4th week, taper before the event", () => {
  const plan = buildHikePlan({ profile: dayHike, data: { today: TODAY, sessions: hikes }, today: TODAY });
  const longs = plan.weeks.filter(item => !item.eventWeek).map(item => item.longMinutes);
  longs.slice(1).forEach((minutes, index) => assert.ok(minutes <= Math.ceil(longs[index] * 1.1 / 5) * 5 + 5 || plan.weeks[index].phase === "Tehermentesítés", `week ${index + 2}: ${minutes} after ${longs[index]}`));
  assert.equal(plan.weeks[3].phase, "Tehermentesítés");
  assert.ok(plan.weeks[3].longMinutes < plan.weeks[2].longMinutes);
  const last = plan.weeks.at(-1);
  assert.equal(last.phase, "Taper");
  assert.ok(last.eventWeek && last.sessions.some(item => item.date === "2027-01-17" && item.title.includes("Mátrabérc")));
  assert.ok(plan.summary.longestMinutes <= plan.summary.dayMinutes * 0.75 + 5, "the full day is saved for the event");
  assert.ok(plan.summary.ready);
});

test("combined training at least three times a week, with descent and uphill work while building", () => {
  const plan = buildHikePlan({ profile: dayHike, data: { today: TODAY, sessions: hikes }, today: TODAY });
  for (const item of plan.weeks.filter(entry => !entry.eventWeek && entry.phase !== "Taper")) {
    const strength = item.sessions.filter(session => session.type === "Erő").length;
    assert.ok(strength === 2 && item.sessions.length >= 4, `week ${item.index}: ${item.sessions.length} sessions, ${strength} strength`);
  }
  const notes = hikeSessions(plan).map(item => item.note).join(" ");
  assert.match(notes, /lejtő a lényeg/);
  assert.ok(hikeSessions(plan).some(item => item.title === "Emelkedős intervall"));
  // no hard climbing intervals in the taper or event week
  plan.weeks.filter(item => item.phase === "Taper").forEach(item => assert.ok(!item.sessions.some(session => session.title === "Emelkedős intervall")));
});

test("trek: pack weight builds in ≤2 kg steps, back-to-back weekends after the base phase, every event day saved", () => {
  const plan = buildHikePlan({ profile: trek, data: { today: TODAY, sessions: hikes }, today: TODAY });
  const packs = plan.weeks.map(item => item.packKg);
  packs.slice(1).forEach((kg, index) => assert.ok(kg - packs[index] <= 2, `pack ${packs[index]} → ${kg}`));
  assert.equal(Math.max(...packs), 12);
  const firstBackToBack = plan.weeks.findIndex(item => item.sessions.some(session => session.title.startsWith("Második túranap")));
  assert.ok(firstBackToBack > 0 && ["Építés", "Tehermentesítés", "Eseményspecifikus"].includes(plan.weeks[firstBackToBack].phase));
  const eventDays = hikeSessions(plan).filter(item => item.title.includes("túranap: Kéktúra"));
  assert.deepEqual(eventDays.map(item => item.date), ["2027-02-27", "2027-02-28", "2027-03-01", "2027-03-02", "2027-03-03"]);
  assert.equal(plan.summary.taperWeeks, 2);
});

test("warnings: no Garmin hikes, too little time, altitude, very long day", () => {
  const plan = buildHikePlan({ profile: { ...dayHike, eventDate: "2026-11-15", hikeKm: 45, hikeGainM: 2500, hikeMaxAltitudeM: 2700 }, data: { today: TODAY, sessions: [] }, today: TODAY });
  const text = plan.warnings.join(" ");
  assert.match(text, /nincs Garmin-túraadat/);
  assert.match(text, /minimális felkészülési ideje 6 hét/);
  assert.match(text, /2500 m fölé/);
  assert.match(text, /sötétben megtett szakasszal/);
  assert.equal(plan.summary.ready, false);
  assert.match(plan.warnings[0], /rövidebb útvonalat/);
  const high = buildHikePlan({ profile: { ...trek, hikeMaxAltitudeM: 3400 }, data: { today: TODAY, sessions: hikes }, today: TODAY });
  assert.match(high.warnings.join(" "), /500 m-rel nőjön/);
});

test("plans are valid calendar items and every source has a link", () => {
  const plan = buildHikePlan({ profile: trek, data: { today: TODAY, sessions: hikes }, today: TODAY });
  for (const item of hikeSessions(plan)) {
    assert.ok(["Túrázás", "Erő", "Kardió"].includes(item.type), item.type);
    assert.ok(item.duration >= 10 && item.duration <= 1440 && item.rpe >= 1 && item.rpe <= 10);
    assert.match(item.id, /^event-trek-\d{4}-\d{2}-\d{2}-\d+$/);
  }
  assert.equal(new Set(hikeSessions(plan).map(item => item.id)).size, hikeSessions(plan).length);
  assert.ok(hikeSessions(plan).filter(isLong).length > 5);
  HIKE_SOURCES.forEach(source => assert.match(source.url, /^https:\/\//));
});
