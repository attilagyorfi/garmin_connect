import test, { after } from "node:test";
import assert from "node:assert/strict";
import { React, act, alerts, assertAccessible, button, click, close, deferred, fail, load, mockFetch, mount, ok, settle, submit, type } from "./helpers/ui.mjs";

after(close);
const { AssistantPanel } = await load("/src/components/AssistantPanel.jsx");
const CUT = /megszakadt a kapcsolat/;
const proposal = status => ({ id: "act-1", action: "upsert_plan", summary: "Holnapi könnyű futás", reason: "Teszt.", status, before: null, plan: { date: "2026-11-26", type: "Futás", title: "Zone 2 futás", duration: 40, intensity: "könnyű", rpe: 4 } });
const state = (status, conversation) => ({ consent: true, memoryEnabled: true, memory: [], conversation: conversation || [{ role: "user", content: "Mit eddzek?" }, { role: "assistant", content: "Könnyű nap.", actions: [proposal(status)] }], usage: { questions: 1, limit: 15, remaining: 14, tokenBudgetLeft: true } });
// The stream ends without a "done" event: the answer was cut off on the way.
const cutStream = () => { const chunks = [new TextEncoder().encode('{"type":"delta","text":"Holnap könny"}\n')]; return { ok: true, status: 200, headers: { get: () => "application/x-ndjson" }, body: { getReader: () => ({ read: async () => chunks.length ? { done: false, value: chunks.shift() } : { done: true } }) } }; };
const panel = async (server, props = {}) => {
  mockFetch({ "/api/assistant": options => options.method === "POST" ? server.post(JSON.parse(options.body)) : server.get() });
  const page = await mount(React.createElement(AssistantPanel, props));
  await click(page.host.querySelector(".assistant-launcher"));
  return page;
};
const ask = async (page, text) => { await type(page.host.querySelector("textarea"), text); await submit(page.host.querySelector("form")); };

test("a cut-off answer: the reason stays after the reload, until the next action", async () => {
  let reloaded = false;
  const page = await panel({ get: () => ok(reloaded ? state("expired") : state("pending", [])), post: payload => { if (payload.action === "ask") { reloaded = true; return cutStream(); } return ok(state("expired", [])); } });
  await ask(page, "Mit eddzek?");
  assert.equal(alerts(page.host).length, 1); assert.match(alerts(page.host)[0], CUT);
  assert.match(page.host.querySelector(".assistant-proposal").textContent, /Lejárt/);
  assert.equal(page.host.querySelector("textarea").value, "");
  await assertAccessible(page.host);
  await click(page.host.querySelector('button[title="Új beszélgetés"]'));
  assert.deepEqual(alerts(page.host), []);
  await page.unmount();
});
test("a cut-off answer: the reason survives a failing reload too", async () => {
  let down = false;
  const page = await panel({ get: () => down ? fail(503, { error: "Másik hiba." }) : ok(state("pending", [])), post: () => { down = true; return cutStream(); } });
  await ask(page, "Mit eddzek?");
  assert.equal(alerts(page.host).length, 1); assert.match(alerts(page.host)[0], CUT);
  await page.unmount();
});
test("the controls unlock only after the reload, and a late reload never overwrites a newer action", async () => {
  const gate = deferred(); let cut = false;
  const page = await panel({ get: () => cut ? gate.promise : ok(state("pending")), post: payload => { if (payload.action === "ask") { cut = true; return cutStream(); } return ok(state("pending", [])); } });
  await ask(page, "Mit eddzek?");
  assert.equal(page.host.querySelector("textarea").disabled, true);
  assert.equal(button(page.host, "Jóváhagyom").disabled, true);
  await click(page.host.querySelector('button[title="Új beszélgetés"]'));
  assert.equal(page.host.querySelectorAll(".assistant-proposal").length, 0);
  await act(async () => gate.resolve(ok(state("expired")))); await settle();
  assert.equal(page.host.querySelectorAll(".assistant-proposal").length, 0);
  assert.equal(page.host.querySelector("textarea").disabled, false);
  await page.unmount();
});
test("an ordinary send error gives the question back, without a reload", async () => {
  let gets = 0;
  const page = await panel({ get: () => { gets += 1; return ok(state("pending", [])); }, post: () => fail(503, { error: "Az Edzőtárs most nem elérhető." }) });
  await ask(page, "Mit eddzek?");
  assert.deepEqual(alerts(page.host), ["Az Edzőtárs most nem elérhető."]);
  assert.equal(page.host.querySelector("textarea").value, "Mit eddzek?");
  assert.equal(gets, 1);
  await page.unmount();
});
test("a failed decision: the message stays and the proposal state comes from the server", async () => {
  let status = "pending", plansChanged = 0;
  const page = await panel({ get: () => ok(state(status)), post: () => { status = "expired"; return fail(409, { error: "A terv közben megváltozott." }); } }, { onPlansChanged: () => { plansChanged += 1; } });
  await click(button(page.host, "Jóváhagyom"));
  assert.deepEqual(alerts(page.host), ["A terv közben megváltozott."]);
  assert.match(page.host.querySelector(".assistant-proposal").textContent, /Lejárt/);
  assert.ok(!button(page.host, "Jóváhagyom"));
  assert.equal(plansChanged, 0);
  await page.unmount();
});
test("a failed decision with a failing reload keeps the original reason and the proposal", async () => {
  let down = false;
  const page = await panel({ get: () => down ? fail(500, { error: "Másik hiba." }) : ok(state("pending")), post: () => { down = true; return fail(409, { error: "A terv közben megváltozott." }); } });
  await click(button(page.host, "Elutasítom"));
  assert.deepEqual(alerts(page.host), ["A terv közben megváltozott."]);
  assert.equal(button(page.host, "Elutasítom").disabled, false);
  await page.unmount();
});
test("an approved proposal stays approved when refreshing the calendar fails", async () => {
  let gets = 0;
  const page = await panel({ get: () => { gets += 1; return ok(state("pending")); }, post: () => ok({ ...state("applied"), decision: { id: "act-1", status: "applied" } }) }, { onPlansChanged: async () => { throw new Error("cloud-state-unavailable"); } });
  await click(button(page.host, "Jóváhagyom"));
  assert.match(page.host.querySelector(".assistant-proposal").textContent, /Bekerült a Naptárba/);
  assert.equal(alerts(page.host).length, 1); assert.match(alerts(page.host)[0], /Naptár nem frissült/);
  assert.equal(gets, 1);
  await page.unmount();
});
