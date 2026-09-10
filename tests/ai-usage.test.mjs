import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import {
  completeGeneration,
  dailyTokenLimit,
  estimateCostUsd,
  reserveGeneration,
  usageTotals,
} from "../server/ai-usage.js";

const userId = "11111111-1111-4111-8111-111111111111";
const generationId = "22222222-2222-4222-8222-222222222222";
const settings = [
  "HYBRID_AI_DAILY_TOKEN_LIMIT",
  "HYBRID_AI_INPUT_USD_PER_MILLION",
  "HYBRID_AI_OUTPUT_USD_PER_MILLION",
];

async function withSettings(values, run) {
  const original = Object.fromEntries(settings.map((key) => [key, process.env[key]]));
  for (const key of settings) {
    if (values[key] === undefined) delete process.env[key];
    else process.env[key] = String(values[key]);
  }
  try {
    return await run();
  } finally {
    for (const key of settings) {
      if (original[key] === undefined) delete process.env[key];
      else process.env[key] = original[key];
    }
  }
}

function fakeClient({ used = 0, rowCount = 1, failOn, failure } = {}) {
  const calls = [];
  return {
    calls,
    async query(sql, params = []) {
      calls.push({ sql: sql.replace(/\s+/g, " ").trim(), params });
      if (failOn?.test(sql)) throw failure || new Error("simulated database failure");
      if (/SELECT COALESCE\(SUM/.test(sql)) return { rows: [{ used: String(used) }] };
      return { rows: [], rowCount };
    },
  };
}

function request(overrides = {}) {
  return {
    userId, id: generationId, model: "test/model", system: "Személyes adat: privát edzésjegyzet.",
    messages: [{ role: "user", content: "Mit jelent a mai terhelésem?" }], maxOutputTokens: 700,
    ...overrides,
  };
}

test("reservation locks the user's transaction before reading and inserting quota usage", async () => {
  await withSettings({ HYBRID_AI_DAILY_TOKEN_LIMIT: 10000 }, async () => {
    const client = fakeClient({ used: 27 });
    const input = request();
    assert.deepEqual(await reserveGeneration(input, client), { allowed: true, usedTokens: 27, limitTokens: 10000 });
    const transaction = client.calls.slice(client.calls.findIndex((call) => call.sql === "BEGIN"));
    assert.equal(transaction.length, 5);
    assert.equal(transaction[0].sql, "BEGIN");
    assert.match(transaction[1].sql, /pg_advisory_xact_lock/);
    assert.deepEqual(transaction[1].params, [`hybrid-ai-quota:${userId}`]);
    assert.match(transaction[2].sql, /SUM\(COALESCE\(total_tokens, reserved_tokens\)\)/);
    assert.match(transaction[2].sql, /WHERE user_id = \$1/);
    assert.match(transaction[2].sql, /Europe\/Budapest/);
    assert.doesNotMatch(transaction[2].sql, /status\s*(?:=|IN)/i);
    assert.deepEqual(transaction[2].params, [userId]);
    assert.match(transaction[3].sql, /^INSERT INTO hybrid_ai_generations/);
    assert.equal(transaction[4].sql, "COMMIT");

    const parameters = transaction[3].params;
    assert.deepEqual(parameters.slice(0, 3), [generationId, userId, "test/model"]);
    assert.equal(parameters[3], createHash("sha256").update(input.system).update(JSON.stringify(input.messages)).digest("hex"));
    assert.ok(parameters[4] >= Buffer.byteLength(input.system + JSON.stringify(input.messages), "utf8") + input.maxOutputTokens);
    assert.ok(!JSON.stringify(client.calls).includes(input.system));
    assert.ok(!JSON.stringify(client.calls).includes(input.messages[0].content));
  });
});

test("daily quota denial rolls back without inserting a generation", async () => {
  await withSettings({ HYBRID_AI_DAILY_TOKEN_LIMIT: 10000 }, async () => {
    const client = fakeClient({ used: 9000 });
    assert.deepEqual(await reserveGeneration(request(), client), {
      allowed: false, reason: "daily_limit", usedTokens: 9000, limitTokens: 10000,
    });
    assert.equal(client.calls.at(-1).sql, "ROLLBACK");
    assert.ok(!client.calls.some((call) => /^(?:INSERT|COMMIT)/.test(call.sql)));
  });
});

test("an oversized request is denied before opening a database transaction", async () => {
  await withSettings({ HYBRID_AI_DAILY_TOKEN_LIMIT: 2000 }, async () => {
    const client = fakeClient();
    assert.deepEqual(await reserveGeneration(request(), client), {
      allowed: false, reason: "request_too_large", limitTokens: 2000,
    });
    assert.equal(client.calls.length, 0);
  });
});

test("database errors roll back the reservation and propagate the original failure", async () => {
  await withSettings({}, async () => {
    const failure = new Error("insert unavailable");
    const client = fakeClient({ failOn: /^INSERT/, failure });
    await assert.rejects(reserveGeneration(request(), client), (error) => error === failure);
    assert.equal(client.calls.at(-1).sql, "ROLLBACK");
    assert.equal(client.calls.filter((call) => call.sql === "ROLLBACK").length, 1);
    assert.ok(!client.calls.some((call) => call.sql === "COMMIT"));
  });
});

test("finalization is scoped to the owner and records actual provider usage", async () => {
  await withSettings({ HYBRID_AI_INPUT_USD_PER_MILLION: 3, HYBRID_AI_OUTPUT_USD_PER_MILLION: 15 }, async () => {
    const client = fakeClient();
    await completeGeneration({ userId, id: generationId, usage: { inputTokens: 1000, outputTokens: 200 } }, client);
    assert.match(client.calls[0].sql, /WHERE id = \$6 AND user_id = \$7 AND status = 'reserved'/);
    assert.deepEqual(client.calls[0].params, ["complete", 1000, 200, 1200, 0.006, generationId, userId]);

    const unavailable = fakeClient({ rowCount: 0 });
    await assert.rejects(completeGeneration({ userId, id: generationId, usage: {} }, unavailable), /reservation unavailable/);
    assert.equal(unavailable.calls[0].params[6], userId);
  });
});

test("missing or incomplete provider totals retain the reservation rather than billing zero", async () => {
  await withSettings({}, async () => {
    for (const usage of [undefined, null, {}, { inputTokens: 250 }, { outputTokens: 40 }, { inputTokens: NaN, outputTokens: 40 }]) {
      const client = fakeClient();
      await completeGeneration({ userId, id: generationId, usage }, client);
      const params = client.calls[0].params;
      assert.equal(params[0], "unconfirmed");
      assert.equal(params[3], null);
      assert.equal(params[4], null);
      assert.doesNotMatch(client.calls[0].sql, /reserved_tokens\s*=/);
    }
  });
});

test("uncertain provider failures preserve the reservation even with partial usage", async () => {
  await withSettings({}, async () => {
    const client = fakeClient();
    await completeGeneration({ userId, id: generationId, status: "error", usage: { inputTokens: 100, outputTokens: 20 } }, client);
    assert.deepEqual(client.calls[0].params.slice(0, 5), ["unconfirmed", 100, 20, null, null]);
  });
});

test("reported aggregate usage is kept when larger than the token breakdown", () => {
  assert.deepEqual(usageTotals({ inputTokens: 100, outputTokens: 20, totalTokens: 150 }), { input: 100, output: 20, total: 150 });
  assert.deepEqual(usageTotals({ totalTokens: 150 }), { input: null, output: null, total: 150 });
  assert.deepEqual(usageTotals({ inputTokens: 100, outputTokens: 20, totalTokens: 10 }), { input: 100, output: 20, total: 120 });
});

test("invalid token limits fall back to the default and valid positive integers are accepted", () => {
  for (const value of [undefined, "", " ", "0", "-1", "12.5", "NaN", "Infinity", "9007199254740992", "abc"]) {
    assert.equal(dailyTokenLimit({ HYBRID_AI_DAILY_TOKEN_LIMIT: value }), 50000, String(value));
  }
  assert.equal(dailyTokenLimit({ HYBRID_AI_DAILY_TOKEN_LIMIT: " 12000 " }), 12000);
});

test("unconfigured or invalid prices are unknown, while explicitly free prices produce zero", () => {
  assert.equal(estimateCostUsd(100, 100, {}), null);
  assert.equal(estimateCostUsd(100, 100, { HYBRID_AI_INPUT_USD_PER_MILLION: "3" }), null);
  for (const value of ["NaN", "Infinity", "-1", "abc"]) {
    assert.equal(estimateCostUsd(100, 100, { HYBRID_AI_INPUT_USD_PER_MILLION: value, HYBRID_AI_OUTPUT_USD_PER_MILLION: "15" }), null);
    assert.equal(estimateCostUsd(100, 100, { HYBRID_AI_INPUT_USD_PER_MILLION: "3", HYBRID_AI_OUTPUT_USD_PER_MILLION: value }), null);
  }
  assert.equal(estimateCostUsd(100, 100, { HYBRID_AI_INPUT_USD_PER_MILLION: "0", HYBRID_AI_OUTPUT_USD_PER_MILLION: "0" }), 0);
  assert.equal(estimateCostUsd(1000000, 100000, { HYBRID_AI_INPUT_USD_PER_MILLION: "3", HYBRID_AI_OUTPUT_USD_PER_MILLION: "15" }), 4.5);
});
