import {
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  gateway,
  generateText,
} from "ai";
import { completeGeneration, reserveGeneration } from "../server/ai-usage.js";

const MAX_MESSAGES = 10;
const MAX_INPUT_CHARACTERS = 24000;
const outputLimit = Number(process.env.HYBRID_AI_MAX_OUTPUT_TOKENS || 700);
const MAX_OUTPUT_TOKENS = Number.isFinite(outputLimit) ? Math.max(256, Math.min(1200, Math.floor(outputLimit))) : 700;
const MODEL_ID = process.env.HYBRID_AI_MODEL || "anthropic/claude-sonnet-5";

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

function sourceSummary(context) {
  const workouts = context.recentWorkouts || [];
  const dates = workouts.map((item) => item.date || item.startTimeLocal || item.startTimeGMT).filter(Boolean).map(String).sort();
  const period = dates.length ? `${dates[0].slice(0, 10)} – ${dates.at(-1).slice(0, 10)}` : "a legutóbbi elérhető szinkron";
  const used = [
    context.readiness != null && `terhelhetőség: ${context.readiness}/100`,
    context.week?.load != null && `heti terhelés: ${context.week.load} pont`,
    workouts.length && `${workouts.length} legutóbbi edzés`,
    context.todayCheckIn && "mai állapotfelmérés",
  ].filter(Boolean).join("; ");
  return `\n\n---\n**Felhasznált adatok** · Időszak: ${period}. ${used || "Nem állt rendelkezésre számszerű személyes mérőszám."}`;
}

function requestsMutation(question) {
  return /(módosíts|változtass|írd át|töröld|add hozzá|hozz létre).*(terv|profil|cél|edzés)/iu.test(question);
}

function localDate(offsetDays = 0) {
  const date = new Date(Date.now() + offsetDays * 86400000);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Budapest", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(date).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function planDateFromQuestion(question) {
  const iso = question.match(/\b(20\d{2}-\d{2}-\d{2})\b/)?.[1];
  if (iso) return iso;
  if (/holnap/iu.test(question)) return localDate(1);
  if (/\bma(i|ra)?\b/iu.test(question)) return localDate();
  return null;
}

function planTypeFromQuestion(question) {
  const types = [
    [/fut/iu, "Futás"], [/erő|súlyz|kond/iu, "Erő"], [/túrá/iu, "Túrázás"],
    [/kerék|bring/iu, "Kerékpár"], [/mobil/iu, "Mobilitás"], [/pihen/iu, "Pihenő"],
    [/kardió/iu, "Kardió"],
  ];
  return types.find(([pattern]) => pattern.test(question))?.[1] || null;
}

function buildPlanProposal(question, plans) {
  if (!requestsMutation(question) || /profil|cél/iu.test(question)) return null;
  const date = planDateFromQuestion(question);
  const type = planTypeFromQuestion(question);
  const candidates = (plans || []).filter((item) => (!date || item.date === date) && (!type || item.type === type));
  const deleting = /töröld|vedd ki|távolítsd/iu.test(question);
  const creating = /add hozzá|hozz létre|új edzés/iu.test(question);
  const existing = candidates.length === 1 ? candidates[0] : null;
  if (deleting) {
    if (!existing) return null;
    return { action: "delete_plan", targetPlanId: existing.id, plan: null, summary: `${existing.title} törlése (${existing.date})`, reason: "A felhasználó kifejezetten az edzés törlését kérte." };
  }
  if (!creating && !existing) return null;
  if (creating && (!date || !type)) return null;
  const duration = Number(question.match(/\b(\d{1,3})\s*perc/iu)?.[1] || existing?.duration || (type === "Pihenő" ? 0 : 60));
  const intensity = ["regeneráló", "könnyű–közepes", "közepes–magas", "könnyű", "közepes", "magas"].find((value) => question.toLocaleLowerCase("hu-HU").includes(value)) || existing?.intensity || "közepes";
  const rpe = Number(question.match(/\bRPE\s*([1-9]|10)\b/iu)?.[1] || existing?.rpe || 5);
  const plan = {
    ...(existing || {}), id: existing?.id || "", date: date || existing.date, type: type || existing.type,
    title: existing?.title || `${type} edzés`, duration, intensity, rpe,
    purpose: existing?.purpose || "", note: existing?.note || "",
  };
  return {
    action: "upsert_plan", targetPlanId: null, plan,
    summary: `${plan.title}: ${plan.date}, ${plan.duration} perc, ${plan.intensity}`,
    reason: existing ? "A felhasználó a meglévő edzésterv módosítását kérte." : "A felhasználó új edzést kért a tervbe.",
  };
}

async function registerProposal(request, proposal) {
  const response = await fetch(`${baseUrl(request)}/api/assistant-actions`, {
    method: "POST",
    headers: { "content-type": "application/json", cookie: request.headers.get("cookie") || "" },
    body: JSON.stringify({ proposal }), cache: "no-store",
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || "A javaslat nem menthető.");
  return response.json();
}

function fallbackAnswer(context, question, reason = "provider") {
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
  const explanation = {
    daily_limit: "A következő válaszhoz már nem maradt elég a mai AI-keretből. A keret budapesti idő szerint éjfélkor újraindul.",
    request_too_large: "Ez a beszélgetés túl hosszú a beállított napi AI-kerethez. Rövidebb kérdéssel vagy új beszélgetéssel próbálkozhatsz.",
    accounting: "Az AI-használati keret most nem ellenőrizhető. Próbáld újra később.",
    provider: "A külső AI-szolgáltatás jelenleg nem érhető el.",
  }[reason] || "A külső AI-szolgáltatás jelenleg nem érhető el.";
  return `${readinessText} ${lastText}\n\n**Gyakorlati értelmezés:** ${advice}\n\n_Ezt a választ az alkalmazás helyi magyarázó motorja készítette a saját adataidból. ${explanation}_`;
}

export async function handle(request, {
  readOwnData = ownData, generate = generateText,
  reserve = reserveGeneration, complete = completeGeneration,
  enabled = ["1", "true", "yes", "on"].includes(String(process.env.HYBRID_AI_ENABLED || "false").toLowerCase()),
} = {}) {
  if (!enabled) {
    return json({ error: "Az AI-asszisztens ebben a zárt kiadásban még nincs bekapcsolva.", code: "ai_disabled" }, 503);
  }
  try {
    const body = await request.json();
    if (!Array.isArray(body?.messages) || body.messages.length === 0) {
      return json({ error: "A kérdés nem lehet üres." }, 400);
    }
    const inputSize = JSON.stringify(body.messages).length;
    if (body.messages.length > 40 || inputSize > MAX_INPUT_CHARACTERS) {
      return json({ error: "A beszélgetés túl hosszú. Töröld az előzményeket, majd próbáld újra." }, 413);
    }
    const [authResponse, dashboardResponse, stateResponse] = await Promise.all([
      readOwnData(request, "/api/auth"),
      readOwnData(request, "/api/dashboard"),
      readOwnData(request, "/api/state"),
    ]);
    if (authResponse.status === 401 || dashboardResponse.status === 401 || stateResponse.status === 401) {
      return json({ error: "A beszélgetéshez bejelentkezés szükséges." }, 401);
    }
    if (!authResponse.ok || !dashboardResponse.ok || !stateResponse.ok) {
      return json({ error: "A személyes sportadatok most nem érhetők el." }, 503);
    }
    const [auth, dashboard, state] = await Promise.all([authResponse.json(), dashboardResponse.json(), stateResponse.json()]);
    if (!auth.user?.id) return json({ error: "A beszélgetéshez bejelentkezés szükséges." }, 401);
    const context = compactContext(dashboard, state);
    const messages = await convertToModelMessages(body.messages.slice(-MAX_MESSAGES));
    const system = `Te a Hybrid Athlete magyar nyelvű, közérthető sportadat-asszisztense vagy. Kizárólag az alábbi, bejelentkezett felhasználóhoz tartozó kontextust használd személyes állításokhoz. Ne találj ki hiányzó adatot. A mérőszámokat laikus nyelven magyarázd. Ne diagnosztizálj és ne ígérj biztos eredményt; egészségügyi panasz vagy veszélyjel esetén javasolj megfelelő szakembert. A válasz legyen tömör, gyakorlatias és magyar nyelvű. Profil-, cél- vagy edzésterv-módosítást soha ne hajts végre közvetlenül: csak jól elkülönített előnézetet adj, mondd ki, hogy még semmit nem módosítottál, és kérj kifejezett felhasználói jóváhagyást.\n\nSZEMÉLYES KONTEXTUS:\n${JSON.stringify(context)}`;
    const lastQuestion = body.messages.at(-1)?.parts?.find((part) => part.type === "text")?.text || "";
    const stream = createUIMessageStream({
      execute: async ({ writer }) => {
        const id = crypto.randomUUID();
        const generationId = crypto.randomUUID();
        let answer;
        let savedProposal = null;
        let reserved = false;
        try {
          const admission = await reserve({
            userId: auth.user.id, id: generationId, model: MODEL_ID,
            system, messages, maxOutputTokens: MAX_OUTPUT_TOKENS,
          });
          if (!admission.allowed) {
            answer = fallbackAnswer(context, lastQuestion, admission.reason);
          } else {
            reserved = true;
            const result = await generate({
              model: gateway(MODEL_ID),
              maxOutputTokens: MAX_OUTPUT_TOKENS,
              maxRetries: 0,
              system, messages,
            });
            answer = result.text;
            await complete({ userId: auth.user.id, id: generationId, usage: result.usage })
              .catch(() => console.warn("chat_usage_complete_failed"));
            console.info("chat_generation", JSON.stringify({ id: generationId, model: MODEL_ID, inputTokens: result.usage?.inputTokens, outputTokens: result.usage?.outputTokens }));
          }
        } catch (error) {
          console.warn(reserved ? "chat_gateway_fallback" : "chat_accounting_unavailable");
          answer = fallbackAnswer(context, lastQuestion, reserved ? "provider" : "accounting");
          if (reserved) await complete({ userId: auth.user.id, id: generationId, status: "error" })
            .catch(() => console.warn("chat_usage_complete_failed"));
        }
        if (requestsMutation(lastQuestion)) {
          const proposal = buildPlanProposal(lastQuestion, state.plans || []);
          if (proposal) {
            try {
              savedProposal = await registerProposal(request, proposal);
              answer = `**Módosítási előnézet**\n\n${answer}\n\n_Még semmit nem módosítottam._`;
            } catch (error) {
              console.warn("chat_proposal_rejected", error?.message || error);
              answer += "\n\n_A javaslatot nem tudtam biztonságosan előkészíteni, ezért semmi nem változott._";
            }
          } else {
            answer += "\n\n_A végrehajtható előnézethez írd meg egyértelműen az edzés dátumát, típusát és a kívánt változtatást. Semmit nem módosítottam._";
          }
        }
        answer += sourceSummary(context);
        writer.write({ type: "text-start", id });
        writer.write({ type: "text-delta", id, delta: answer });
        writer.write({ type: "text-end", id });
        if (savedProposal) writer.write({ type: "data-plan-proposal", id: savedProposal.id, data: savedProposal });
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
