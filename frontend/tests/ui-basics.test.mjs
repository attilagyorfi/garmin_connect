import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { React, assertAccessible, button, close, dashboard, load, mockFetch, mount, ok, session, settle, testProfile } from "./helpers/ui.mjs";
import * as dates from "../src/lib/dates.js";

after(close);
const css = () => readdirSync(new URL("../src/", import.meta.url)).filter(name => name.endsWith(".css")).map(name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8")).join("\n");
const day = value => new Date(`${value}T12:00:00`);
const SUNDAY = "2026-11-22", MONDAY = "2026-11-23", TUESDAY = "2026-11-24";
const h = React.createElement;

test("Összefüggések: the weekly suggestion stays, without buttons that do nothing", async () => {
  mockFetch({ "/api/dashboard": () => ok(dashboard()), "/api/model": () => ok({}) });
  const { InsightsPage } = await load("/src/pages/InsightsPage.jsx");
  const page = await mount(h(InsightsPage, { profile: testProfile })), card = page.host.querySelector(".coach-card");
  assert.match(card.textContent, /HETI JAVASLAT/);
  assert.ok(card.querySelector("h2").textContent.trim());
  assert.match(card.querySelector("p").textContent, /Tartsd a kiegyensúlyozott/);
  assert.equal(card.querySelectorAll("button").length, 0);
  assert.doesNotMatch(page.host.textContent, /EGYETÉRT|MÉG NEM/i);
  assert.doesNotMatch(css(), /coach-actions/);
  await page.unmount();
});

const sidebar = async props => { const { Sidebar } = await load("/src/components/Sidebar.jsx"); return mount(h(Sidebar, { collapsed: false, onToggle() {}, onActive() {}, active: "Ma", profile: testProfile, locked: [], garminStatus: null, ...props })); };
const menu = host => [...host.querySelectorAll("nav button, [data-tour='settings']")];
test("Menü: every item keeps its name when the label is hidden", async () => {
  for (const collapsed of [false, true]) {
    const page = await sidebar({ collapsed, active: "Insights" }), names = menu(page.host).map(node => node.getAttribute("aria-label"));
    assert.deepEqual(names, ["Áttekintés", "Ma", "Naptár", "Trendek", "Cél", "Összefüggések", "Hol tartasz?", "Napló", "Profil", "Beállítások"]);
    assert.deepEqual(menu(page.host).map(node => node.textContent.trim()), names);
    assert.deepEqual(menu(page.host).map(node => node.dataset.tour), ["Áttekintés", "Ma", "Naptár", "Trendek", "Cél", "Insights", "Hol tartasz?", "Napló", "Profil", "settings"]);
    assert.deepEqual([...page.host.querySelectorAll("[aria-current]")].map(node => [node.getAttribute("aria-label"), node.getAttribute("aria-current")]), [["Összefüggések", "page"]]);
    await assertAccessible({ include: [["nav"], [".side-bottom"]] });
    await page.unmount();
  }
});
test("Menü: the lock is part of the name, its icon is not read again; Settings can be current", async () => {
  const calls = [], page = await sidebar({ active: "Beállítások", locked: ["Naptár", "Insights"], onActive: key => calls.push(key) });
  const locked = menu(page.host).filter(node => node.disabled);
  assert.deepEqual(locked.map(node => node.getAttribute("aria-label")), ["Naptár, zárolva", "Összefüggések, zárolva"]);
  for (const node of locked) {
    assert.equal(node.title, "Az első Garmin-szinkron után nyílik meg");
    assert.equal(node.getAttribute("aria-disabled"), "true");
    assert.equal(node.querySelector(".nav-lock").getAttribute("aria-hidden"), "true");
    assert.equal(node.querySelector(".nav-lock").hasAttribute("aria-label"), false);
  }
  assert.deepEqual([...page.host.querySelectorAll('[aria-current="page"]')].map(node => node.textContent.trim()), ["Beállítások"]);
  button(page.host, "Trendek").click(); button(page.host, "Beállítások").click(); button(page.host, "Naptár").click();
  assert.deepEqual(calls, ["Trendek", "Beállítások"]);
  await page.unmount();
});

test("the rest day comes from the profile, never from the day of the week", () => {
  const { isPlannedRestDay } = dates, monday = { restDay: "H", trainingDays: ["K", "Sze", "Cs", "P", "Szo", "V"] };
  assert.equal(isPlannedRestDay(monday, day(SUNDAY)), false);
  assert.equal(isPlannedRestDay(monday, day(MONDAY)), true);
  assert.equal(isPlannedRestDay({ restDay: "V", trainingDays: ["H"] }, day(SUNDAY)), true);
  assert.equal(isPlannedRestDay({ restDay: "V", trainingDays: ["H"] }, day(TUESDAY)), false);
  for (const restDay of [undefined, null, "", "vasárnap"]) {
    assert.equal(isPlannedRestDay({ restDay, trainingDays: ["H", "V"] }, day(SUNDAY)), false);
    assert.equal(isPlannedRestDay({ restDay, trainingDays: ["H", "V"] }, day(TUESDAY)), true);
  }
  for (const profile of [null, undefined, {}, { restDay: "?", trainingDays: [] }, { trainingDays: "H,K" }]) assert.equal(isPlannedRestDay(profile, day(SUNDAY)), false);
});
const calendar = async (props, data = dashboard([])) => { mockFetch({ "/api/dashboard": () => ok(data) }); const { PersistentCalendarPage } = await load("/src/pages/PersistentCalendarPage.jsx"); return mount(h(PersistentCalendarPage, { profile: testProfile, cloudState: { plans: [], feedback: {} }, onCloudPatch() {}, onNavigate() {}, ...props })); };
test("Naptár: an empty Sunday is a rest day only if the profile says so", async () => {
  const restOnMonday = { ...testProfile, restDay: "H", trainingDays: ["K", "Sze", "Cs", "P", "Szo", "V"] };
  for (const [profile, initialDate, text] of [[restOnMonday, SUNDAY, "Erre a napra nincs edzés."], [restOnMonday, MONDAY, "Tervezett pihenőnap."], [testProfile, SUNDAY, "Tervezett pihenőnap."], [{ ...testProfile, restDay: "", trainingDays: [] }, SUNDAY, "Erre a napra nincs edzés."]]) {
    const page = await calendar({ profile, initialDate });
    assert.equal(page.host.querySelector(".selected-day-sessions").textContent, text);
    await page.unmount();
  }
});

test("explanations: time budget, zone rows and calendar cells get their own term", async () => {
  const { ExplainabilityLayer } = await load("/src/components/Explainability.jsx");
  const page = await mount(h("div", null,
    h("div", { className: "weekly-recap" }, h("div", null, h("span", null, "82%IDŐKERET"), h("span", null, "5ó 10pEDZÉSIDŐ"))),
    h("div", { className: "goal-progress" }, "8óHETI IDŐKERET"),
    h("div", { className: "zone-row" }, h("b", null, "Z1"), h("strong", null, "10p")),
    h("div", { className: "calendar-grid" }, ["ErőFelső test · 60p", "FutásZone 2 futás · 50p", "Kardió2 edzés · 90p"].map(text => h("button", { key: text }, h("div", null, text)))),
    h(ExplainabilityLayer, { page: "teszt" })));
  await settle();
  const metric = selector => [...page.host.querySelectorAll(selector)].map(node => node.dataset.metric);
  assert.deepEqual(metric(".weekly-recap span"), ["Időkeret", "Edzésidő"]);
  assert.deepEqual(metric(".goal-progress"), ["Időkeret"]);
  assert.deepEqual(metric(".zone-row"), ["Pulzuszóna"]);
  assert.deepEqual(metric(".calendar-grid>button>div"), ["Edzésidő", "Edzésidő", "Edzésidő"]);
  assert.equal(page.host.querySelector(".goal-progress").textContent, "8óHETI IDŐKERET");
  await page.unmount();
});
test("Naptár: the legend lists only the states a cell can have", async () => {
  const plan = { id: "p1", date: SUNDAY, type: "Erő", title: "Felső test", duration: 60, intensity: "közepes", rpe: 6, status: "planned" };
  const page = await calendar({ initialDate: SUNDAY, cloudState: { plans: [plan], feedback: {} } }, dashboard([session("a1", MONDAY)]));
  assert.deepEqual([...page.host.querySelectorAll(".calendar-legend i")].map(node => node.className), ["planned", "done"]);
  assert.deepEqual([...new Set([...page.host.querySelectorAll(".calendar-grid>button>div")].map(node => node.className))].sort(), ["done", "planned"]);
  assert.doesNotMatch(css(), /calendar-legend \.extra/);
  await page.unmount();
});
