import test from "node:test";
import assert from "node:assert/strict";
import { buildTrainingInterpretation, percentChange, summarizeTrainingPeriods } from "../src/lib/periods.js";

const profile = { goal: "Hibrid teljesítmény" };

test("periods are equal length, adjacent and exclude the future", () => {
  const result = summarizeTrainingPeriods([
    { date: "2026-09-14", durationMin: 60, load: 50, type: "Futás" },
    { date: "2026-09-08", durationMin: 30, load: 20, type: "Erő" },
    { date: "2026-09-07", durationMin: 45, load: 40, type: "Futás" },
    { date: "2026-09-15", durationMin: 99, load: 99, type: "Futás" },
  ], 7, "2026-09-14");
  assert.equal(result.current.count, 2);
  assert.equal(result.current.minutes, 90);
  assert.equal(result.current.strengthRatio, 50);
  assert.equal(result.previous.count, 1);
  assert.equal(result.previous.load, 40);
});

test("an unknown value keeps the sum unknown instead of zero", () => {
  const result = summarizeTrainingPeriods([{ date: "2026-09-14", durationMin: null, load: 5 }], 7, "2026-09-14");
  assert.equal(result.current.minutes, null);
  assert.equal(result.current.load, 5);
});

test("change is not computed against an empty previous period", () => {
  assert.equal(percentChange(10, 0), null);
  const text = buildTrainingInterpretation(summarizeTrainingPeriods([{ date: "2026-09-14", durationMin: 30, load: 10 }], 30, "2026-09-14"), profile).items[0][1];
  assert.match(text, /előző 30 napból nincs összehasonlítható edzés/);
});

test("no sessions in the period is reported, not treated as zero training", () => {
  const result = buildTrainingInterpretation(summarizeTrainingPeriods([], 7, "2026-09-14"), profile);
  assert.match(result.note, /Korlátozott értékelés/);
});

test("load rising faster than time is interpreted as an intensity shift", () => {
  const sessions = [
    { date: "2026-09-14", durationMin: 60, load: 120 },
    { date: "2026-09-07", durationMin: 60, load: 60 },
  ];
  const result = buildTrainingInterpretation(summarizeTrainingPeriods(sessions, 7, "2026-09-14"), profile);
  assert.match(result.items[1][1], /gyorsabban nőtt, mint az edzésidő/);
  assert.match(result.items[2][1], /ne növeld egyszerre/);
});
