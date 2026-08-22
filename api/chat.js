import {
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  gateway,
  generateText,
} from "ai";

const MAX_MESSAGES = 10;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "private, no-store" },
  });
}

function baseUrl(request) {
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

function fallbackAnswer(context, question) {
  const readiness = Number(context.readiness);
  const week = context.week || {};
  const recent = context.recentWorkouts || [];
  const last = recent.at(-1);
  const readinessText = Number.isFinite(readiness)
    ? `A mai terhelhetőséged ${readiness}/100, ami ${readiness >= 75 ? "jó terhelhetőséget" : readiness >= 50 ? "közepes, óvatosan terhelhető állapotot" : "alacsony terhelhetőséget és nagyobb regenerációs igényt"} jelez.`
    : "A mai terhelhetőségi pontszám nem áll rendelkezésre.";
  const weekText = week.load != null
    ? `A heti terhelésed ${week.load} pont${week.target ? ` a ${week.target} pontos keretből` : ""}.`
    : "A heti terhelési kerethez jelenleg nincs elég adat.";
  const lastText = last
    ? `A legutóbbi rögzített edzésed: ${last.type || last.name || "edzés"}${last.durationMin ? `, ${last.durationMin} perc` : ""}.`
    : "Nem találtam friss edzést a rendelkezésre álló adatokban.";
  const lower = question.toLocaleLowerCase("hu-HU");
  let advice = readiness >= 75
    ? "A mai adatok alapján beleférhet a tervezett edzés, de az intenzitást a közérzetedhez igazítsd."
    : readiness >= 50
      ? "Ma inkább könnyű–közepes terhelést válassz, és csökkents az intenzitáson, ha romlik a közérzeted."
      : "Ma a regeneráció, könnyű átmozgatás vagy pihenés a biztonságosabb irány.";
  if (/pihen|regener|fárad|alv/.test(lower)) advice = readiness >= 70
    ? "A pontszám önmagában nem indokol teljes pihenőt, de az alvás, izomláz és fáradtság jelzéseit vedd elsődlegesnek."
    : "A jelenlegi terhelhetőség alapján indokolt lehet a terhelés csökkentése és több regeneráció.";
  if (/terhel|fejlő|változ|trend/.test(lower)) advice = `${weekText} A fejlődést több hét trendje alapján érdemes megítélni, nem egyetlen napi értékből.`;
  return `${readinessText} ${lastText}\n\n**Gyakorlati értelmezés:** ${advice}\n\n_Ezt a választ az alkalmazás helyi magyarázó motorja készítette a saját adataidból, mert a külső AI-szolgáltatás jelenleg nem érhető el._`;
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
      execute: async ({ writer }) => {
        const id = crypto.randomUUID();
        let answer;
        try {
          const result = await generateText({
            model: gateway("anthropic/claude-sonnet-5"),
            system: `Te a Hybrid Athlete magyar nyelvű, közérthető sportadat-asszisztense vagy. Kizárólag az alábbi, bejelentkezett felhasználóhoz tartozó kontextust használd személyes állításokhoz. Ne találj ki hiányzó adatot. Röviden nevezd meg, mely adatok támasztják alá a választ. A mérőszámokat laikus nyelven magyarázd. Ne diagnosztizálj és ne ígérj biztos eredményt; egészségügyi panasz vagy veszélyjel esetén javasolj megfelelő szakembert. A válasz legyen tömör, gyakorlatias és magyar nyelvű.\n\nSZEMÉLYES KONTEXTUS:\n${JSON.stringify(context)}`,
            messages,
          });
          answer = result.text;
        } catch (error) {
          console.warn("chat_gateway_fallback", error?.message || error);
          const lastQuestion = body.messages.at(-1)?.parts?.find((part) => part.type === "text")?.text || "";
          answer = fallbackAnswer(context, lastQuestion);
        }
        writer.write({ type: "text-start", id });
        writer.write({ type: "text-delta", id, delta: answer });
        writer.write({ type: "text-end", id });
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
  const protocol = req.headers["x-forwarded-proto"] || "https";
  const origin = `${protocol}://${req.headers.host}`;
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
