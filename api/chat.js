import {
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  gateway,
  streamText,
} from "ai";

const MAX_MESSAGES = 10;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "private, no-store" },
  });
}

function baseUrl(request) {
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return new URL(request.url).origin;
}

async function ownData(request, path) {
  return fetch(`${baseUrl(request)}${path}`, {
    headers: { cookie: request.headers.get("cookie") || "" },
    cache: "no-store",
  });
}

function compactContext(dashboard, state) {
  const workouts = Array.isArray(dashboard?.workouts) ? dashboard.workouts.slice(-14) : [];
  const trends = Array.isArray(dashboard?.trends) ? dashboard.trends.slice(-12) : [];
  return {
    profile: state?.profile || {},
    todayCheckIn: state?.todayCheckIn || state?.checkin || null,
    readiness: dashboard?.readiness,
    readinessBand: dashboard?.readinessBand,
    decision: dashboard?.decision,
    metrics: dashboard?.metrics,
    week: dashboard?.week,
    recentWorkouts: workouts,
    recentTrends: trends,
  };
}

async function handle(request) {
  try {
    const body = await request.json();
    if (!Array.isArray(body?.messages) || body.messages.length === 0) {
      return json({ error: "A kérdés nem lehet üres." }, 400);
    }
    const [dashboardResponse, stateResponse] = await Promise.all([
      ownData(request, "/api/dashboard"),
      ownData(request, "/api/state"),
    ]);
    if (dashboardResponse.status === 401 || stateResponse.status === 401) {
      return json({ error: "A beszélgetéshez bejelentkezés szükséges." }, 401);
    }
    if (!dashboardResponse.ok || !stateResponse.ok) {
      return json({ error: "A személyes sportadatok most nem érhetők el." }, 503);
    }
    const context = compactContext(await dashboardResponse.json(), await stateResponse.json());
    const messages = await convertToModelMessages(body.messages.slice(-MAX_MESSAGES));
    const stream = createUIMessageStream({
      execute: ({ writer }) => {
        const result = streamText({
          model: gateway("anthropic/claude-sonnet-5"),
          system: `Te a Hybrid Athlete magyar nyelvű, közérthető sportadat-asszisztense vagy. Kizárólag az alábbi, bejelentkezett felhasználóhoz tartozó kontextust használd személyes állításokhoz. Ne találj ki hiányzó adatot. Röviden nevezd meg, mely adatok támasztják alá a választ. A mérőszámokat laikus nyelven magyarázd. Ne diagnosztizálj és ne ígérj biztos eredményt; egészségügyi panasz vagy veszélyjel esetén javasolj megfelelő szakembert. A válasz legyen tömör, gyakorlatias és magyar nyelvű.\n\nSZEMÉLYES KONTEXTUS:\n${JSON.stringify(context)}`,
          messages,
        });
        writer.merge(result.toUIMessageStream());
      },
    });
    return createUIMessageStreamResponse({ stream });
  } catch (error) {
    console.error("chat_error", error);
    return json({ error: "Az asszisztens jelenleg nem tud válaszolni. Próbáld újra később." }, 500);
  }
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Nem támogatott művelet." });
    return;
  }
  const origin = `https://${process.env.VERCEL_URL || req.headers.host}`;
  const request = new Request(`${origin}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json", cookie: req.headers.cookie || "" },
    body: JSON.stringify(req.body || {}),
  });
  const response = await handle(request);
  res.statusCode = response.status;
  response.headers.forEach((value, key) => res.setHeader(key, value));
  if (!response.body) {
    res.end();
    return;
  }
  const reader = response.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    res.write(Buffer.from(value));
  }
  res.end();
}
