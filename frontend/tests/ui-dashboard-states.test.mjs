import test, { after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { React, act, alerts, assertAccessible, budapestDay, button, click, close, dashboard, deferred, fail, load, mockFetch, mount, noData, ok, refresh, session, settle, statuses, submit, testProfile, type } from "./helpers/ui.mjs";

after(close);
beforeEach(() => localStorage.clear());
const h = React.createElement, RETRY = "Próbáld újra", LOADING = /Töltjük az adataidat/, FAILED = /Nem sikerült betölteni az adataidat/, STALE = /Nem sikerült frissíteni az adataidat/, EMPTY = /Még nincs szinkronizált Garmin-adat/;
const PAST = budapestDay(-21);
const pastPlan = { id: "p1", date: PAST, type: "Futás", title: "Mentett terv", duration: 45, intensity: "könnyű", rpe: 4, purpose: "", note: "", status: "planned", matchedActivityId: "garmin-42" };
const todayPlan = { ...pastPlan, id: "p2", date: budapestDay(), type: "Erő", title: "Mai erő", matchedActivityId: "" };
const cloud = { plans: [pastPlan, todayPlan], feedback: {}, checkins: {} };
// Nothing may be claimed about training while the data is unknown.
const FALSE_CLAIMS = /nincs edzés|\b0 edzés|NINCS TERV|elmaradt|\b0%|0 \/ 0|Felkészültség: \d|Még nincs értékelhető hét|még nincs terv vagy edzés|Nincs teljesítés|mintaadatokat látsz/i;
const PAGES = {
  "Napló": { path: "LiveJournalPage", props: { cloudState: cloud }, ready: host => host.querySelector(".activity-row")?.textContent.includes("Teszt futás") && host.querySelector(".weekly-closure"), changed: host => host.textContent.includes("Friss futás") },
  "Naptár": { path: "PersistentCalendarPage", props: { cloudState: cloud }, ready: host => host.querySelector(".selected-actual")?.textContent.includes("Teszt futás"), changed: host => host.textContent.includes("Friss futás") },
  "Cél": { path: "GoalPage", props: { cloudState: cloud }, ready: host => host.querySelector(".goal-score") && host.querySelector(".goal-gaps") && host.querySelector(".adaptive-card") && host.textContent.includes("48p"), changed: host => host.textContent.includes("90p") },
  "Hol tartasz?": { path: "BenchmarksPage", props: {}, ready: host => host.textContent.includes("Napi lépésszám"), changed: host => host.textContent.includes("40 éves") },
  "Trendek": { path: "LiveTrendsPage", props: {}, ready: host => host.querySelector(".zone-row") && !host.querySelector(".trend-state") && !host.querySelector(".decision-translation-state"), changed: host => host.textContent.includes("77p") },
  "Összefüggések": { path: "InsightsPage", props: {}, ready: host => host.querySelector(".decision-translation-grid") && !host.querySelector(".decision-translation-state"), changed: host => host.textContent.includes("Friss javaslat") },
};
const STATE_PAGES = ["Napló", "Naptár", "Cél", "Hol tartasz?"];
const fresh = () => dashboard([session("run-1"), { ...session("run-2", budapestDay(), "Friss futás"), durationMin: 90 }], { zones: [0, 77, 0, 0, 0], week: { total_load: 420, change_pct: 4, recommendations: ["Friss javaslat."] }, benchmarks: { ...dashboard().benchmarks, profile: { sex: "male", age: 40 } } });
// server.next is the answer of the next dashboard request: a value, a promise or a function.
const open = async (name, server, props = {}) => {
  mockFetch({ "/api/dashboard": () => { server.calls = (server.calls || 0) + 1; return typeof server.next === "function" ? server.next() : server.next; }, "/api/model": () => ok({}) });
  const module = await load(`/src/pages/${PAGES[name].path}.jsx`);
  return mount(h(module[PAGES[name].path], { profile: testProfile, onCloudPatch() {}, onNavigate() {}, onEdit() {}, ...PAGES[name].props, ...props }));
};

for (const name of STATE_PAGES) test(`${name}: loading, error with retry and truly empty are three different states`, async () => {
  const gate = deferred(), server = { next: gate.promise };
  let page = await open(name, server);
  assert.ok(statuses(page.host).some(text => LOADING.test(text)), "nincs betöltésjelzés");
  assert.deepEqual(alerts(page.host), []);
  assert.doesNotMatch(page.host.textContent, FALSE_CLAIMS);
  await act(async () => gate.resolve(fail(500))); await settle();
  assert.equal(alerts(page.host).length, 1); assert.match(alerts(page.host)[0], FAILED);
  assert.doesNotMatch(page.host.textContent, /Töltjük/);
  assert.doesNotMatch(page.host.textContent, FALSE_CLAIMS);
  await assertAccessible(page.host);
  server.next = () => { throw new TypeError("Failed to fetch"); };
  await click(button(page.host, RETRY));
  assert.match(alerts(page.host)[0], FAILED);
  server.next = ok(dashboard());
  await click(button(page.host, RETRY));
  assert.equal(server.calls, 3);
  assert.deepEqual(alerts(page.host), []);
  assert.ok(!button(page.host, RETRY));
  assert.ok(PAGES[name].ready(page.host), "az újrapróbálás után nincs ott az adat");
  await page.unmount();
  page = await open(name, { next: noData() });
  assert.ok(statuses(page.host).some(text => EMPTY.test(text)), "nincs üres állapot");
  assert.deepEqual(alerts(page.host), []);
  assert.ok(!button(page.host, RETRY));
  assert.doesNotMatch(page.host.textContent, /Töltjük|Felkészültség: \d|mintaadat/);
  await assertAccessible(page.host);
  await page.unmount();
  // A 404 without the known code and a malformed answer are errors, not "no data yet".
  for (const answer of [fail(404), ok(null), ok([])]) { page = await open(name, { next: answer }); assert.match(alerts(page.host)[0] || "", FAILED); await page.unmount(); }
});

for (const name of Object.keys(PAGES)) test(`${name}: a refresh never takes the visible data away`, async () => {
  const server = { next: ok(dashboard()) }, page = await open(name, server), gate = deferred();
  assert.ok(PAGES[name].ready(page.host));
  server.next = gate.promise; await refresh();
  assert.ok(PAGES[name].ready(page.host), "frissítés közben eltűnt az adat");
  assert.doesNotMatch(page.host.textContent, /Töltjük/);
  await act(async () => gate.resolve(fail(500))); await settle();
  assert.ok(PAGES[name].ready(page.host), "sikertelen frissítés után eltűnt az adat");
  const shown = STATE_PAGES.includes(name);
  assert.equal(alerts(page.host).length, shown ? 1 : 0);
  if (shown) { assert.match(alerts(page.host)[0], STALE); await assertAccessible(page.host); }
  server.next = ok(fresh());
  if (shown) await click(button(page.host, RETRY)); else await refresh();
  assert.ok(PAGES[name].changed(page.host), "nem látszik a friss adat");
  assert.deepEqual(alerts(page.host), []);
  await page.unmount();
});

test("useDashboardState: an answer that was asked for earlier never replaces a newer one", async () => {
  const { useDashboardState } = await load("/src/lib/api.js"), seen = [];
  const Probe = () => { seen.push(useDashboardState()); return null; }, last = () => seen.at(-1);
  const answers = [deferred(), deferred(), deferred(), deferred()]; let index = 0;
  mockFetch({ "/api/dashboard": () => answers[index++].promise });
  const page = await mount(h(Probe));
  assert.equal(last().status, "loading");
  await refresh();
  await act(async () => answers[1].resolve(ok({ version: "új" }))); await settle();
  await act(async () => answers[0].resolve(ok({ version: "régi" }))); await settle();
  assert.deepEqual([last().status, last().data.version], ["ready", "új"]);
  await act(async () => { last().reload(); }); await refresh();
  await act(async () => answers[3].resolve(ok({ version: "legújabb" }))); await settle();
  await act(async () => answers[2].resolve(fail(500))); await settle();
  assert.deepEqual([last().status, last().data.version, last().refreshError], ["ready", "legújabb", false]);
  answers.push(deferred(), deferred());
  await refresh(); await act(async () => answers[4].reject(new Error("hálózat"))); await settle();
  assert.deepEqual([last().status, last().data.version, last().refreshError], ["ready", "legújabb", true]);
  await refresh(); await act(async () => answers[5].resolve(noData())); await settle();
  assert.deepEqual([last().status, last().data, last().refreshError], ["empty", null, false]);
  await page.unmount();
  // Nothing is kept between mounts: the next account starts from scratch.
  answers.push(deferred()); const next = await mount(h(Probe));
  assert.deepEqual([last().status, last().data], ["loading", null]);
  await next.unmount();
});

test("Napló: no match for a filter and no synced workout have their own messages", async () => {
  let page = await open("Napló", { next: ok(dashboard()) });
  await type(page.host.querySelector('input[aria-label="Keresés"]'), "nincs ilyen");
  assert.match(page.host.querySelector(".empty").textContent, /Ehhez a kereséshez vagy szűréshez nincs edzés/);
  await page.unmount();
  page = await open("Napló", { next: ok(dashboard([])) });
  assert.match(page.host.querySelector(".empty").textContent, /A szinkronizált adataidban még nincs edzés/);
  assert.doesNotMatch(page.host.textContent, /Ehhez a kereséshez/);
  await page.unmount();
});
test("Napló: a refresh does not reopen or swap the opened workout, and its draft stays", async () => {
  const server = { next: ok(dashboard()) }, page = await open("Napló", server, { initialActivityId: "run-1" });
  const note = () => page.host.querySelector(".activity-modal textarea");
  assert.ok(note()); await type(note(), "Piszkozat");
  server.next = ok(fresh()); await refresh();
  assert.equal(note().value, "Piszkozat");
  await click(page.host.querySelector(".modal .close"));
  server.next = ok(dashboard()); await refresh();
  assert.ok(!page.host.querySelector(".activity-modal"));
  await page.unmount();
});

const summary = host => [...host.querySelectorAll(".calendar-week-summary strong")].map(node => node.textContent.trim());
for (const [label, next, text] of [["hiba", () => fail(500), "Az edzéseidet most nem látjuk."], ["betöltés", () => new Promise(() => {}), "Az edzéseidet még töltjük."]]) test(`Naptár (${label}): saved plans stay visible and editable, nothing false is claimed`, async () => {
  const patches = [], page = await open("Naptár", { next }, { initialDate: PAST, onCloudPatch: patch => patches.push(patch) });
  assert.match(page.host.querySelector(".selected-plan").textContent, /Mentett terv/);
  assert.match(page.host.querySelector(".calendar-grid").textContent, /Mentett terv/);
  assert.doesNotMatch(page.host.textContent, FALSE_CLAIMS);
  assert.deepEqual(summary(page.host), ["1", "—", "45p / —", "—", "—"]);
  await click(button(page.host, "SZERKESZTÉS"));
  const select = () => page.host.querySelector('select[aria-label="Garmin-edzés kézi párosítása"]');
  assert.equal(select().value, "garmin-42");
  assert.match(select().closest(".field").textContent, /Az edzéseidet most nem látjuk|Az edzéseidet még töltjük/);
  await assertAccessible(page.host);
  await type(page.host.querySelector('input[aria-label="Edzés neve"]'), "Átírt terv");
  await click(button(page.host, "Edzésterv mentése"));
  assert.equal(patches.length, 1);
  assert.deepEqual([patches[0].plan.title, patches[0].plan.matchedActivityId], ["Átírt terv", "garmin-42"]);
  await click([...page.host.querySelectorAll(".calendar-grid>button")].find(node => !node.querySelector("div")));
  assert.equal(page.host.querySelector(".selected-day-sessions").textContent, text);
  await page.unmount();
});
test("Naptár: with data the pairing, the missed plan and the summary work as before", async () => {
  const page = await open("Naptár", { next: ok(dashboard([session("other", budapestDay(-100))])) }, { initialDate: PAST });
  assert.match(page.host.querySelector(".plan-comparison").textContent, /ELMARADT/);
  assert.deepEqual(summary(page.host), ["1", "0", "45p / nincs edzés", "0%", "0 / 0"]);
  await page.unmount();
});
test("Naptár: an open editor keeps its draft while the data arrives", async () => {
  const gate = deferred(), server = { next: gate.promise }, page = await open("Naptár", server, { initialDate: PAST });
  await click(button(page.host, "SZERKESZTÉS"));
  const title = () => page.host.querySelector('input[aria-label="Edzés neve"]');
  await type(title(), "Piszkozat");
  await act(async () => gate.resolve(ok(dashboard()))); await settle();
  assert.equal(title().value, "Piszkozat");
  assert.match(page.host.querySelector('select[aria-label="Garmin-edzés kézi párosítása"]').textContent, /Teszt futás/);
  server.next = fail(500); await refresh();
  assert.equal(title().value, "Piszkozat");
  await page.unmount();
});

test("Cél: without data only the goal, the steps and the goal editing stay", async () => {
  const edits = [], profile = { ...testProfile, eventName: "Tavaszi futás", eventDate: budapestDay(60), eventType: "half" };
  for (const next of [() => new Promise(() => {}), fail(500), noData()]) {
    const page = await open("Cél", { next }, { profile, onEdit: () => edits.push(1) });
    assert.ok(!page.host.querySelector(".goal-score,.goal-components,.goal-gaps,.event-planner,.periodization-card,.adaptive-card"));
    assert.match(page.host.querySelector(".goal-hero h2").textContent, /Tavaszi futás/);
    assert.ok(page.host.querySelector(".planning-flow"));
    await click(button(page.host, "CÉL SZERKESZTÉSE"));
    await page.unmount();
  }
  assert.equal(edits.length, 3);
});
test("Cél: the requested planner opens when the data arrives, and its draft survives refreshes", async () => {
  const gate = deferred(), server = { next: gate.promise }, page = await open("Cél", server, { initialAdaptiveOpen: true });
  assert.ok(!page.host.querySelector(".adaptive-modal"));
  await act(async () => gate.resolve(ok(dashboard()))); await settle();
  const title = () => page.host.querySelector(".adaptive-modal .adaptive-title");
  await type(title(), "Saját cím");
  for (const answer of [fail(500), ok(fresh())]) { server.next = answer; await refresh(); assert.equal(title().value, "Saját cím"); }
  await page.unmount();
});

const app = async server => {
  localStorage.setItem("hybrid-onboarding-version", "2"); sessionStorage.setItem("hybrid-splash-shown", "1");
  mockFetch({
    "/api/auth": options => options.method === "DELETE" ? ok({}) : ok({ user: options.method === "POST" ? { id: "b", email: "b@example.test", name: "B" } : { id: "a", email: "a@example.test", name: "A" } }),
    "/api/state": () => ok({ profile: testProfile, accent: "teal", checkins: {}, feedback: {}, plans: [], tour: { status: "done", version: 1 } }),
    "/api/garmin": () => server.garmin ? server.garmin() : ok({ status: "connected", email_hint: "a•••@example.test" }),
    "/api/dashboard": () => typeof server.next === "function" ? server.next() : server.next,
    "/api/model": () => ok({}), "/api/sessions": () => ok({ sessions: [] }),
    "/api/sync": () => ok({ run_id: "r1", status: "completed", progress: 100 }),
  });
  const { App } = await load("/src/App.jsx");
  return mount(h(App));
};
const lockedCount = host => host.querySelectorAll(".sidebar nav button.locked").length;
const content = host => host.querySelector(".content").textContent;
const nav = (host, label) => click([...host.querySelectorAll(".sidebar button")].find(node => node.textContent.trim() === label));

test("App: a failing first check shows an error with retry, not the first sync", async () => {
  for (const first of [fail(500), fail(404), () => { throw new TypeError("Failed to fetch"); }]) {
    const server = { next: first }, page = await app(server);
    assert.doesNotMatch(content(page.host), /Első Garmin-szinkron/);
    assert.equal(alerts(page.host).length, 1); assert.match(alerts(page.host)[0], FAILED);
    assert.equal(lockedCount(page.host), 7);
    await assertAccessible(page.host);
    server.next = fail(503); await click(button(page.host, RETRY));
    assert.match(alerts(page.host)[0], FAILED);
    server.next = ok(dashboard()); await click(button(page.host, RETRY));
    assert.equal(lockedCount(page.host), 0); assert.deepEqual(alerts(page.host), []);
    await page.unmount();
  }
});
test("App: the real 404 still opens the first-sync gate, also after a retry", async () => {
  const server = { next: noData() }; let page = await app(server);
  assert.match(content(page.host), /Első Garmin-szinkron/); assert.equal(lockedCount(page.host), 7);
  await page.unmount();
  server.next = fail(500); page = await app(server);
  server.next = noData(); await click(button(page.host, RETRY));
  assert.match(content(page.host), /Első Garmin-szinkron/); assert.deepEqual(alerts(page.host), []);
  await page.unmount();
});
test("App: a failing check after a sync closes neither the pages nor the menu", async () => {
  const server = { next: ok(dashboard()) }, page = await app(server);
  await nav(page.host, "Áttekintés");
  assert.equal(lockedCount(page.host), 0);
  server.next = fail(500);
  await click([...page.host.querySelectorAll(".content button")].find(node => /szinkron|frissít/i.test(node.textContent)));
  await settle(60);
  assert.equal(lockedCount(page.host), 0, "a menü bezárult");
  assert.doesNotMatch(content(page.host), /Első Garmin-szinkron/);
  await nav(page.host, "Napló");
  assert.match(alerts(page.host)[0], FAILED);
  server.next = noData();
  await nav(page.host, "Áttekintés");
  await click([...page.host.querySelectorAll(".content button")].find(node => /szinkron|frissít/i.test(node.textContent)));
  await settle(60);
  assert.match(content(page.host), /Első Garmin-szinkron/);
  await page.unmount();
});
test("App: a late answer of the previous account never opens the new account's pages", async () => {
  const late = deferred(), lateGarmin = deferred(), second = deferred(), server = { next: () => late.promise, garmin: () => lateGarmin.promise }, page = await app(server);
  server.garmin = () => new Promise(() => {}); // the Settings card asks for it as well
  await nav(page.host, "Beállítások");
  await click([...page.host.querySelectorAll(".content button")].find(node => /^Kijelentkezés$/.test(node.textContent.trim())));
  server.next = () => second.promise; server.garmin = () => ok({ status: "disconnected" });
  await type(page.host.querySelector('input[type="email"]'), "b@example.test"); await type(page.host.querySelector('input[type="password"]'), "jelszo-teszt-12");
  await submit(page.host.querySelector(".auth-card form"));
  assert.match(content(page.host), /Megnézzük az adataidat/);
  await act(async () => { late.resolve(ok(dashboard())); lateGarmin.resolve(ok({ status: "connected", email_hint: "a•••@example.test" })); }); await settle();
  assert.equal(lockedCount(page.host), 7, "a régi fiók válasza megnyitotta a menüt");
  assert.match(content(page.host), /Megnézzük az adataidat/);
  assert.match(page.host.querySelector(".sidebar .profile").textContent, /Nincs Garmin-kapcsolat/);
  await act(async () => second.resolve(noData())); await settle();
  assert.match(content(page.host), /Első Garmin-szinkron/);
  await page.unmount();
});
