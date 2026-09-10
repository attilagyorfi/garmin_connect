import assert from "node:assert/strict";
import test from "node:test";
import { handle } from "../api/chat.js";

const userId = "11111111-1111-4111-8111-111111111111";
const request = () => new Request("https://app.example/api/chat", { method: "POST", body: JSON.stringify({
  userId: "untrusted-browser-id", inputTokens: 0,
  messages: [{ id: "question", role: "user", parts: [{ type: "text", text: "Hogyan változott a terhelésem?" }] }],
}) });
const readOwnData = async (_request, path) => Response.json({
  "/api/auth": { user: { id: userId } },
  "/api/state": { profile: {}, plans: [] },
  "/api/dashboard": { readiness: 75, workouts: [], week: { load: 100 } },
}[path]);

function dependencies(overrides = {}) {
  return { readOwnData, reserve: async () => ({ allowed: true }),
    generate: async () => ({ text: "Tesztválasz", usage: { inputTokens: 100, outputTokens: 10 } }),
    complete: async () => {}, ...overrides };
}

test("denied quota produces a local explanation without a provider call", async () => {
  for (const reason of ["daily_limit", "request_too_large"]) {
    let called = false;
    const response = await handle(request(), dependencies({ reserve: async () => ({ allowed: false, reason }),
      generate: async () => { called = true; throw new Error("must not generate"); } }));
    const text = await response.text();
    assert.equal(called, false);
    assert.match(text, /helyi magyarázó motorja/);
    assert.match(text, reason === "daily_limit" ? /éjfélkor/ : /túl hosszú/);
  }
});

test("accounting outage fails closed with a different explanation", async () => {
  let called = false;
  const response = await handle(request(), dependencies({ reserve: async () => { throw new Error("database unavailable"); },
    generate: async () => { called = true; } }));
  assert.match(await response.text(), /keret most nem ellenőrizhető/);
  assert.equal(called, false);
});

test("only authenticated user and provider usage are used for billing", async () => {
  let reservation, completion;
  const response = await handle(request(), dependencies({
    reserve: async (input) => { reservation = input; return { allowed: true }; },
    generate: async (input) => {
      assert.equal(input.system, reservation.system);
      assert.deepEqual(input.messages, reservation.messages);
      assert.equal(input.maxRetries, 0);
      return { text: "Tesztválasz", usage: { inputTokens: 100, outputTokens: 10 } };
    }, complete: async (input) => { completion = input; },
  }));
  assert.match(await response.text(), /Tesztválasz/);
  assert.equal(reservation.userId, userId);
  assert.equal(completion.userId, userId);
  assert.equal(completion.id, reservation.id);
  assert.deepEqual(completion.usage, { inputTokens: 100, outputTokens: 10 });
});

test("missing provider usage is not changed to a zero-token completion", async () => {
  let completion;
  const response = await handle(request(), dependencies({
    generate: async () => ({ text: "Válasz fogyasztási adatok nélkül" }),
    complete: async (input) => { completion = input; },
  }));
  await response.text();
  assert.equal(completion.usage, undefined);
});

test("uncertain provider failure waits for finalization before finishing the response", async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let completion, finished = false;
  const response = await handle(request(), dependencies({
    generate: async () => { throw new Error("provider disconnected"); },
    complete: async (input) => { completion = input; await gate; },
  }));
  const result = response.text().then((text) => { finished = true; return text; });
  await new Promise(setImmediate);
  assert.equal(completion.status, "error");
  assert.equal(completion.usage, undefined);
  assert.equal(finished, false);
  release();
  assert.match(await result, /helyi magyarázó motorja/);
});

test("missing authentication stops before accounting or generation", async () => {
  let reserved = false;
  const response = await handle(request(), dependencies({
    readOwnData: async (_request, path) => path === "/api/auth" ? Response.json({}, { status: 401 }) : readOwnData(_request, path),
    reserve: async () => { reserved = true; },
  }));
  assert.equal(response.status, 401);
  assert.equal(reserved, false);
});
