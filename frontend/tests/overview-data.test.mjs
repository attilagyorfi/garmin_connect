import test from "node:test";
import assert from "node:assert/strict";
import { overviewData, budapestToday } from "../src/overviewData.js";
test("missing data never becomes zero or sample trends", () => {
  const result = overviewData(null, 30, "2026-09-14");
  assert.equal(result.known, false); assert.equal(result.load, null); assert.deepEqual(result.points, []);
});
test("range uses current date, excludes future sessions, and keeps multiple daily sessions", () => {
  const result = overviewData({ today: "2026-08-01", sessions: [
    { date: "2026-08-15", load: 9, durationMin: 10 },
    { date: "2026-09-14", load: 3, durationMin: 20 },
    { date: "2026-09-14", load: 4, durationMin: 40 },
    { date: "2026-09-15", load: 9, durationMin: 10 },
  ], readiness: 65 }, 30, "2026-09-14");
  assert.equal(result.from, "2026-08-16"); assert.equal(result.sessions.length, 2);
  assert.equal(result.load, 7); assert.equal(result.minutes, 60); assert.equal(result.readiness, null);
});
test("missing numeric values remain unknown while genuine zero is valid", () => {
  assert.equal(overviewData({ sessions: [{date: "2026-09-14", load: null}] },30,"2026-09-14").load,null);
  assert.equal(overviewData({ sessions: [] },30,"2026-09-14").load,0);
});
test("trends are date-filtered and preserve gaps", () => {
  const result = overviewData({trends:[{date:"2026-09-14",ctl:3,atl:null},{date:"2026-01-01",ctl:9}]},30,"2026-09-14");
  assert.equal(result.points.length,1); assert.equal(result.points[0].atl,null);
});
test("Budapest day handles UTC midnight boundary", () => {
  assert.equal(budapestToday(new Date("2026-09-13T23:00:00Z")),"2026-09-14");
});
