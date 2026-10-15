import test from "node:test";
import assert from "node:assert/strict";
import { TOUR_STEPS, TOUR_VERSION, availableSteps } from "../src/lib/tourSteps.js";

test("steps without a visible anchor are skipped, centred steps always stay", () => {
  const present = new Set(["nav", "Ma", "settings"]);
  const shown = availableSteps(TOUR_STEPS, target => present.has(target));
  assert.equal(shown[0].target, null);
  assert.equal(shown.at(-1).target, null);
  assert.deepEqual(shown.filter(step => step.target).map(step => step.target), ["nav", "Ma", "settings"]);
});

test("every step has a Hungarian title and text, and the tour is versioned", () => {
  assert.ok(TOUR_VERSION >= 1);
  for (const step of TOUR_STEPS) assert.ok(step.title && step.text.length > 40, step.title);
  assert.ok(TOUR_STEPS.some(step => step.target === "settings" && /indíthatod újra/.test(step.text)));
});
