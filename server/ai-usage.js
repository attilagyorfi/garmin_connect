// Server-only accounting. Never accept usage totals or user IDs from the browser.
import { createHash } from "node:crypto";
import pg from "pg";

let pool;
function database() {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL || process.env.POSTGRES_URL;
    if (!connectionString) throw new Error("AI accounting database unavailable");
    pool = new pg.Pool({ connectionString, max: 3, connectionTimeoutMillis: 10000, idleTimeoutMillis: 10000 });
    pool.on("error", () => console.warn("ai_accounting_connection_error"));
  }
  return pool;
}

export function dailyTokenLimit(env = process.env) {
  const value = String(env.HYBRID_AI_DAILY_TOKEN_LIMIT ?? "").trim();
  const number = Number(value);
  return /^\d+$/.test(value) && Number.isSafeInteger(number) && number > 0 ? number : 50000;
}

function tokenCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

export function estimateCostUsd(inputTokens, outputTokens, env = process.env) {
  const input = String(env.HYBRID_AI_INPUT_USD_PER_MILLION ?? "").trim();
  const output = String(env.HYBRID_AI_OUTPUT_USD_PER_MILLION ?? "").trim();
  const inputRate = Number(input), outputRate = Number(output);
  if (!input || !output || !Number.isFinite(inputRate) || !Number.isFinite(outputRate) || inputRate < 0 || outputRate < 0 || tokenCount(inputTokens) === null || tokenCount(outputTokens) === null) return null;
  return Number(((inputTokens * inputRate + outputTokens * outputRate) / 1000000).toFixed(8));
}

export function usageTotals(usage = {}) {
  const input = tokenCount(usage?.inputTokens), output = tokenCount(usage?.outputTokens);
  const reported = tokenCount(usage?.totalTokens);
  return { input, output, total: input !== null && output !== null ? Math.max(reported ?? 0, input + output) : reported };
}

// A byte-based reservation includes system instructions, context, and message framing.
// It is deliberately conservative; the provider's reported usage settles it afterwards.
export function reservationTokens(system, messages, maxOutputTokens) {
  return Buffer.byteLength(system + JSON.stringify(messages), "utf8") + maxOutputTokens + 2048;
}

const initializeSql = `CREATE TABLE IF NOT EXISTS hybrid_ai_generations (
  id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
  model TEXT NOT NULL, prompt_hash TEXT NOT NULL, status TEXT NOT NULL,
  reserved_tokens INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER, output_tokens INTEGER,
  total_tokens INTEGER, estimated_cost_usd NUMERIC(12,8),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ
)`;
const todaySql = "date_trunc('day', NOW() AT TIME ZONE 'Europe/Budapest') AT TIME ZONE 'Europe/Budapest'";

// The client override is used only by deterministic tests; the handler always uses the database pool.
export async function reserveGeneration({ userId, id, model, system, messages, maxOutputTokens }, clientOverride) {
  const reserved = reservationTokens(system, messages, maxOutputTokens);
  const limit = dailyTokenLimit();
  if (reserved > limit) return { allowed: false, reason: "request_too_large", limitTokens: limit };
  const client = clientOverride || await database().connect();
  let transaction = false;
  try {
    await client.query(initializeSql);
    await client.query("CREATE INDEX IF NOT EXISTS hybrid_ai_generations_user_day_idx ON hybrid_ai_generations(user_id, created_at DESC)");
    await client.query("BEGIN");
    transaction = true;
    await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [`hybrid-ai-quota:${userId}`]);
    const { rows: [row] } = await client.query(`SELECT COALESCE(SUM(COALESCE(total_tokens, reserved_tokens)), 0) AS used
      FROM hybrid_ai_generations WHERE user_id = $1 AND created_at >= ${todaySql}`, [userId]);
    const used = Number(row.used);
    if (used + reserved > limit) {
      await client.query("ROLLBACK");
      transaction = false;
      return { allowed: false, reason: "daily_limit", usedTokens: used, limitTokens: limit };
    }
    await client.query(`INSERT INTO hybrid_ai_generations (id, user_id, model, prompt_hash, status, reserved_tokens)
      VALUES ($1, $2, $3, $4, 'reserved', $5)`, [id, userId, model,
      createHash("sha256").update(system).update(JSON.stringify(messages)).digest("hex"), reserved]);
    await client.query("COMMIT");
    transaction = false;
    return { allowed: true, usedTokens: used, limitTokens: limit };
  } catch (error) {
    if (transaction) await client.query("ROLLBACK");
    throw error;
  } finally {
    if (!clientOverride) client.release();
  }
}

export async function completeGeneration({ userId, id, usage, status = "complete" }, clientOverride) {
  const { input, output, total } = usageTotals(usage);
  // Missing billing data (including uncertain provider failures) retains the reservation.
  const settledStatus = status === "complete" && total !== null ? "complete" : "unconfirmed";
  const client = clientOverride || await database().connect();
  try {
    const result = await client.query(`UPDATE hybrid_ai_generations
      SET status = $1, input_tokens = $2, output_tokens = $3, total_tokens = $4,
          estimated_cost_usd = $5, completed_at = NOW()
      WHERE id = $6 AND user_id = $7 AND status = 'reserved' RETURNING id`,
    [settledStatus, input, output, settledStatus === "complete" ? total : null,
      settledStatus === "complete" ? estimateCostUsd(input, output) : null, id, userId]);
    if (!result.rowCount) throw new Error("AI accounting reservation unavailable");
  } finally {
    if (!clientOverride) client.release();
  }
}
