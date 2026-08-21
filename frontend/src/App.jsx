import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Dumbbell,
  Filter,
  HelpCircle,
  LockKeyhole,
  LogOut,
  Menu,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  TrendingUp,
  UserRound,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import brandMarkUrl from "./assets/hybrid-athlete-mark-on-dark.svg";

const nav = [
  ["Áttekintés", BarChart3],
  ["Ma", Activity],
  ["Naptár", CalendarDays],
  ["Trendek", TrendingUp],
  ["Cél", TrendingUp],
  ["Elemzések", Sparkles],
  ["Napló", ClipboardList],
  ["Profil", UserRound],
];
const heat = [
  1, 2, 1, 0, 2, 2, 3, 1, 2, 3, 2, 1, 3, 2, 2, 1, 0, 2, 3, 1, 2, 3, 3, 2, 1, 2,
  3, 2, 0, 1, 2, 3, 2, 1, 0, 2, 3, 2, 3, 1, 2, 3, 2, 3, 1, 2, 3, 2, 3, 3, 2, 1,
  3, 2, 2, 3, 1, 2, 3, 2, 1, 3, 2, 3, 3, 2, 1, 2, 3, 3, 0, 1, 2, 1, 2, 3, 2, 1,
  3, 2, 2, 3, 1, 2,
];
const metrics = [
  ["HRV (éjszakai)", "62 ms", "+5%", 68, "warn"],
  ["Alvás", "7ó 12p", "+6%", 76, "good"],
  ["Nyugalmi pulzus", "48 bpm", "−3", 82, "good"],
  ["Hibrid TSB", "+4,2", "+2,1", 61, "good"],
];
const trendData = Array.from({ length: 12 }, (_, i) => ({
  week: `${i + 1}. hét`,
  ctl: 32 + i * 1.8 + (i % 3),
  atl: 30 + i * 2 + (i % 2 ? 6 : -2),
  tsb: 5 + (i % 4) * 1.4,
}));
const sessions = [
  [
    "aug. 14.",
    "Futás",
    "Pénteki Z2 – progreszív",
    "46p",
    "138 bpm",
    "5",
    "82",
    "TERV SZERINT",
  ],
  [
    "aug. 12.",
    "Futás",
    "Könnyű Z2 – Margitsziget",
    "1ó 12p",
    "132 bpm",
    "4",
    "68",
    "TERV SZERINT",
  ],
  [
    "aug. 11.",
    "Mobilitás",
    "Csípő és boka mobilitás",
    "18p",
    "—",
    "2",
    "11",
    "EXTRA",
  ],
  [
    "aug. 10.",
    "Erő",
    "Alsótest – progresszív túlterhelés",
    "52p",
    "—",
    "8",
    "76",
    "TERV SZERINT",
  ],
  [
    "aug. 8.",
    "Futás",
    "Tempó intervall",
    "48p",
    "151 bpm",
    "7",
    "94",
    "TERV SZERINT",
  ],
  [
    "aug. 7.",
    "Mobilitás",
    "Mobilitás aktív nap",
    "22p",
    "—",
    "2",
    "14",
    "EXTRA",
  ],
  [
    "aug. 5.",
    "Futás",
    "Z2 alapozás",
    "54p",
    "135 bpm",
    "4",
    "64",
    "TERV SZERINT",
  ],
  [
    "aug. 3.",
    "Túrázás",
    "Dobogókő – 840 m szint",
    "3ó 35p",
    "128 bpm",
    "6",
    "184",
    "CSÚCS",
  ],
];

const metricGlossary = {
  Readiness:
    "A 0–100-as terhelhetőségi pontszám azt becsüli, mennyire áll készen a szervezeted a mai edzésre. A magasabb érték általában több terhelést enged, az alacsonyabb érték regenerációt vagy könnyítést indokol.",
  Bizonyosság:
    "Azt mutatja, mennyire teljesek és következetesek az értékeléshez használt adatok. Alacsony bizonyosságnál az ajánlást óvatosabban érdemes kezelni.",
  "HRV (éjszakai)":
    "A szívverések közötti idő apró változékonysága alvás közben. A saját megszokott értékedhez képest tartós csökkenés fáradtságot vagy stresszt jelezhet; egyetlen nap önmagában nem döntő.",
  Alvás:
    "Az alvás hossza és minősége a regeneráció egyik fő jele. Kevés vagy rossz alvás ronthatja a teljesítményt, a koordinációt és a terheléstűrést.",
  "Nyugalmi pulzus":
    "A nyugalomban mért szívverésszám. A saját alapértékedhez képest szokatlan emelkedés fáradtságot, stresszt vagy kezdődő betegséget jelezhet.",
  TSB: "A rövid és hosszú távú terhelés különbségéből becsült frissesség. Pozitív érték inkább friss állapotot, erősen negatív érték felhalmozott fáradtságot jelez.",
  CTL: "A nagyjából hathetes terhelésből számolt hosszú távú edzettségi szint. Lassan változik; emelkedése tartós munkát, túl gyors növekedése fokozott kockázatot jelenthet.",
  ATL: "Az utóbbi körülbelül egy hét terhelését összegző akut fáradtság. Gyorsan emelkedik egy nehéz blokk után, és pihenéssel gyorsabban csökken, mint a CTL.",
  "CTL · ATL · TSB":
    "CTL: hosszú távú edzettség. ATL: rövid távú fáradtság. TSB: a kettő különbségéből becsült frissesség. Együtt azt mutatják, hogy fejlődik-e a formád, és közben mennyi fáradtságot halmoztál fel.",
  Terhelés:
    "Az edzés időtartamát és intenzitását egy közös pontszámba sűríti. Magasabb szám nagyobb regenerációs igényt jelent; elsősorban a saját korábbi értékeidhez hasonlítsd.",
  Edzésidő:
    "Az adott időszakban edzéssel töltött percek összege. A célhoz viszonyítva megmutatja, hogy a heti terv mennyire reális és teljesíthető.",
  "Erő arány":
    "Megmutatja, a heti edzésidő mekkora része volt erőedzés. A célértéktől való eltérés segít a következő edzéstípus kiválasztásában.",
  RPE: "Az edzés szubjektív nehézsége 1–10-ig. Az 1 nagyon könnyű, a 10 maximális; a tartósan magas RPE több regenerációt vagy kisebb terhelést indokolhat.",
  Pulzus:
    "Az átlagos percenkénti szívverés. A megszokottnál magasabb pulzus azonos tempónál fáradtságra, melegre, folyadékhiányra vagy stresszre utalhat.",
  Pulzuszóna:
    "Az intenzitás pulzus alapján meghatározott tartománya. Z1–Z2 könnyű, aerob munka; Z3 közepes; Z4–Z5 nagy intenzitás, ezért több regenerációt igényel.",
  Z1: "Nagyon könnyű intenzitás: bemelegítéshez, levezetéshez és aktív regenerációhoz használható.",
  Z2: "Könnyű, hosszan fenntartható aerob intenzitás. Az állóképességi alap fejlesztésének fő tartománya.",
  Z3: "Közepes intenzitás. Javítja a tartós tempót, de már számottevő fáradtságot okozhat.",
  Z4: "Nehéz, küszöb körüli intenzitás. Erős fejlesztő inger, ezért célzottan és megfelelő regenerációval érdemes használni.",
  Z5: "Nagyon nagy, csak rövid ideig tartható intenzitás. Jelentős terhelést és hosszabb regenerációs igényt okoz.",
  Táv: "Az edzés során megtett távolság. Önmagában nem mutatja a nehézséget: a tempóval, szintemelkedéssel és pulzussal együtt értelmezendő.",
  Edzésgyakoriság:
    "Az egy hétre jutó edzések átlagos száma. A következetességet jelzi, de a több alkalom nem feltétlenül jobb, ha a regeneráció nem elég.",
  Felkészültség:
    "A célodhoz szükséges következetesség, terhelés, egyensúly, regeneráció és célspecifikusság 0–100-as összesítése. Az alacsonyabb részpontszámok jelölik a fejlesztendő területeket.",
  Időkeret:
    "A vállalt heti edzésidő teljesülési aránya. A tartós elmaradás túl feszes tervet, a tartós túllépés túlzott terhelést jelezhet.",
};
function MetricHelp({ term, children, text }) {
  const explanation = text || metricGlossary[term];
  if (!explanation) return children;
  return (
    <span
      className="metric-help"
      tabIndex="0"
      aria-label={`${term}. ${explanation}`}
    >
      {children}
      <CircleHelp size={15} aria-hidden="true" />
      <span className="metric-tooltip" role="tooltip">
        <b>{term}</b>
        <span>{explanation}</span>
      </span>
    </span>
  );
}
function explanationTerm(text) {
  const value = String(text || "").toUpperCase();
  if (value.includes("CTL") && value.includes("ATL") && value.includes("TSB"))
    return "CTL · ATL · TSB";
  if (value.includes("CTL")) return "CTL";
  if (value.includes("ATL")) return "ATL";
  if (value.includes("TSB")) return "TSB";
  if (value.includes("HRV")) return "HRV (éjszakai)";
  if (value.includes("ALVÁS")) return "Alvás";
  if (value.includes("RPE")) return "RPE";
  if (value.includes("PULZUS") || value.includes("BPM")) return "Pulzus";
  if (/\bZ[1-5]\b/.test(value) || value.includes("ZÓNA")) return "Pulzuszóna";
  if (value.includes("TÁV") || value.includes(" KM")) return "Táv";
  if (value.includes("ERŐ")) return "Erő arány";
  if (value.includes("EDZÉS / HÉT")) return "Edzésgyakoriság";
  if (
    value.includes("IDŐKERET") ||
    value.includes("EDZÉSIDŐ") ||
    value.includes("PERC") ||
    value.includes("ÓRA")
  )
    return "Edzésidő";
  if (value.includes("BIZONYOSSÁG")) return "Bizonyosság";
  if (value.includes("READINESS") || value.includes("FELKÉSZÜLTSÉG"))
    return "Felkészültség";
  if (value.includes("TERHELÉS") || value.includes("LOAD")) return "Terhelés";
  return null;
}
function ExplainabilityLayer({ page }) {
  useEffect(() => {
    const applyExplanations = () => {
      if (document.querySelector(".onboarding-backdrop")) return;
      const selectors = [
        ".ring",
        ".heatmap",
        ".weekbar",
        ".week-stats>div",
        ".trend-summary .card",
        ".zone-row",
        ".goal-progress",
        ".goal-score",
        ".goal-component",
        ".goal-meta span",
        ".finding-score",
        ".weekly-recap>div>span",
        ".activity-stats>span",
        ".plan-comparison",
        ".calendar-grid>button>div",
        ".table-wrap tbody td:nth-child(4)",
        ".table-wrap tbody td:nth-child(5)",
        ".table-wrap tbody td:nth-child(6)",
        ".table-wrap tbody td:nth-child(7)",
        ".table-wrap tbody td:nth-child(8)",
      ];
      document.querySelectorAll(selectors.join(",")).forEach((node) => {
        if (
          node.closest(".metric-help") ||
          node.querySelector?.(".metric-help") ||
          node.hasAttribute("aria-expanded")
        )
          return;
        let term = explanationTerm(node.textContent);
        if (!term && node.matches(".ring")) term = "Readiness";
        if (!term && node.matches(".heatmap")) term = "Terhelés";
        if (!term && node.matches(".weekbar")) term = "Időkeret";
        if (!term && node.matches(".goal-score,.goal-component"))
          term = "Felkészültség";
        if (!term && node.matches(".finding-score")) term = "Bizonyosság";
        if (
          !term &&
          node.matches(
            ".calendar-grid>button>div,.table-wrap tbody td:nth-child(4)",
          )
        )
          term = "Edzésidő";
        if (!term && node.matches(".table-wrap tbody td:nth-child(5)"))
          term = "Pulzus";
        if (!term && node.matches(".table-wrap tbody td:nth-child(6)"))
          term = "Táv";
        if (!term && node.matches(".table-wrap tbody td:nth-child(7)"))
          term = "Terhelés";
        if (!term && node.matches(".table-wrap tbody td:nth-child(8)"))
          term = "RPE";
        if (term && metricGlossary[term]) {
          node.classList.add("explained-value");
          node.tabIndex = node.tabIndex >= 0 ? node.tabIndex : 0;
          node.dataset.metric = term;
          node.dataset.explanation = metricGlossary[term];
          node.setAttribute(
            "aria-label",
            `${node.textContent.trim()}. ${term}: ${metricGlossary[term]}`,
          );
        }
      });
    };
    const timer = setTimeout(applyExplanations, 0);
    const content = document.querySelector(".content");
    const observer = content
      ? new window.MutationObserver(() => applyExplanations())
      : null;
    observer?.observe(content, { childList: true, subtree: true });
    return () => {
      clearTimeout(timer);
      observer?.disconnect();
    };
  }, [page]);
  return null;
}
function MetricHeaderLayer({ page }) {
  useEffect(() => {
    const timer = setTimeout(() => {
      const headers = [
        [".table-wrap th:nth-child(4)", "Edzésidő"],
        [".table-wrap th:nth-child(5)", "Pulzus"],
        [".table-wrap th:nth-child(6)", "Táv"],
        [".table-wrap th:nth-child(7)", "Terhelés"],
        [".table-wrap th:nth-child(8)", "RPE"],
        [".chart-card .section-head .eyebrow", "CTL · ATL · TSB"],
      ];
      headers.forEach(([selector, term]) =>
        document.querySelectorAll(selector).forEach((node) => {
          if (!metricGlossary[term]) return;
          node.classList.add("explained-value", "metric-header-explanation");
          node.tabIndex = 0;
          node.dataset.metric = term;
          node.dataset.explanation = metricGlossary[term];
          node.setAttribute(
            "aria-label",
            `${node.textContent.trim()}. ${term}: ${metricGlossary[term]}`,
          );
        }),
      );
    }, 0);
    return () => clearTimeout(timer);
  }, [page]);
  return null;
}

function useDashboardData() {
  const [data, setData] = useState(null);
  useEffect(() => {
    let active = true;
    fetch("/api/dashboard")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((value) => active && setData(value))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  return data;
}
async function fetchCloudState() {
  const response = await fetch("/api/state");
  if (!response.ok) throw new Error("cloud-state-unavailable");
  return response.json();
}
async function patchCloudState(patch) {
  const response = await fetch("/api/state", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error("cloud-state-save-failed");
  return response.json();
}
function mergeCloudState(current, patch) {
  const next = { ...(current || {}), ...patch };
  if (patch.checkin)
    next.checkins = {
      ...(current?.checkins || {}),
      [patch.checkin.date]: patch.checkin.value,
    };
  if (patch.feedback)
    next.feedback = {
      ...(current?.feedback || {}),
      [patch.feedback.activityId]: patch.feedback.value,
    };
  if (patch.plan)
    next.plans = [
      ...(current?.plans || []).filter((item) => item.id !== patch.plan.id),
      patch.plan,
    ];
  if (patch.plans) {
    const replaceDates = new Set(patch.replacePlanDates || []),
      plans = new Map(
        (current?.plans || [])
          .filter((item) => !replaceDates.has(item.date))
          .map((item) => [item.id, item]),
      );
    patch.plans.forEach((item) => plans.set(item.id, item));
    next.plans = [...plans.values()];
  }
  if (patch.deletePlan)
    next.plans = (current?.plans || []).filter(
      (item) => item.id !== patch.deletePlan,
    );
  delete next.checkin;
  delete next.feedback;
  delete next.plan;
  delete next.deletePlan;
  delete next.replacePlanDates;
  return next;
}
function localCloudSnapshot(profile, accent) {
  const checkins = {};
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key?.startsWith("hybrid-checkin-")) {
      try {
        checkins[key.slice("hybrid-checkin-".length)] = JSON.parse(
          localStorage.getItem(key),
        );
      } catch {}
    }
  }
  let feedbackMap = {};
  try {
    feedbackMap = JSON.parse(
      localStorage.getItem("hybrid-activity-feedback") || "{}",
    );
  } catch {}
  return { profile, accent, checkins, feedbackMap };
}

const goalModes = {
  Futóteljesítmény: {
    title: "Zone 2 futás",
    quality: "Minőségi futóedzés",
    focus: "futóteljesítmény",
  },
  Erőfejlesztés: {
    title: "Technikai erőedzés",
    quality: "Progresszív erőedzés",
    focus: "erőfejlesztés",
  },
  "Hegyi állóképesség": {
    title: "Emelkedős állóképességi edzés",
    quality: "Hegyi specifikus edzés",
    focus: "hegyi állóképesség",
  },
  "Általános egészség": {
    title: "Könnyű aerob átmozgatás",
    quality: "Kiegyensúlyozott teljes testes edzés",
    focus: "általános egészség",
  },
  "Hibrid teljesítmény": {
    title: "Zone 2 alapozás",
    quality: "Minőségi hibrid edzés",
    focus: "hibrid teljesítmény",
  },
};
function personalizeDashboard(data, profile, checkin) {
  const safeProfile = profile || defaultProfile,
    base = data || {},
    mode = goalModes[safeProfile.goal] || goalModes["Hibrid teljesítmény"],
    readiness = Number(base.readiness ?? 78),
    week = base.week || {};
  const sessions = base.sessions || [],
    latest = sessions[0]?.date ? new Date(sessions[0].date) : new Date(),
    weekStart = new Date(latest);
  weekStart.setDate(latest.getDate() - 6);
  const recent = sessions.filter((item) => new Date(item.date) >= weekStart),
    actualMinutes = recent.reduce(
      (sum, item) => sum + Number(item.durationMin || 0),
      0,
    ),
    strengthMinutes = recent
      .filter((item) => item.type === "Erő")
      .reduce((sum, item) => sum + Number(item.durationMin || 0), 0);
  const targetMinutes = Math.max(60, Number(safeProfile.weeklyHours || 8) * 60),
    progress = Math.min(100, Math.round((actualMinutes / targetMinutes) * 100)),
    actualStrength = actualMinutes
      ? Math.round((strengthMinutes / actualMinutes) * 100)
      : 0;
  const available = Math.max(1, safeProfile.trainingDays?.length || 1),
    dailyBudget = Math.max(
      25,
      Math.min(90, Math.round(targetMinutes / available / 5) * 5),
    ),
    remaining = Math.max(0, targetMinutes - actualMinutes);
  const fatiguePenalty = checkin
    ? Math.max(0, (Number(checkin.fatigue) - 2) * 6) +
      Math.max(0, (Number(checkin.stress) - 3) * 4) +
      Math.max(0, (Number(checkin.soreness) - 3) * 4) +
      Math.max(0, (3 - Number(checkin.motivation)) * 3)
    : 0;
  const adjustedReadiness = Math.max(
    0,
    Math.round(
      checkin?.illness
        ? Math.min(readiness - fatiguePenalty, 30)
        : checkin?.pain
          ? Math.min(readiness - fatiguePenalty, 45)
          : readiness - fatiguePenalty,
    ),
  );
  const protectedDay =
    adjustedReadiness < 60 ||
    checkin?.illness ||
    checkin?.pain ||
    /regener|pihenő/i.test(base.decision?.title || "");
  const title = checkin?.illness
    ? "Teljes pihenő"
    : checkin?.pain
      ? "Fájdalommentes mobilitás"
      : protectedDay
        ? base.decision?.title || "Aktív regeneráció"
        : adjustedReadiness >= 80
          ? mode.quality
          : mode.title;
  const duration = protectedDay
    ? base.decision?.duration || "20–45 perc"
    : `${Math.min(dailyBudget, Math.max(30, remaining || dailyBudget))} perc`;
  const goalReason = `A ${safeProfile.goal.toLowerCase()} célodhoz és a heti ${safeProfile.weeklyHours} órás keretedhez igazítva.`;
  const limitationNote = safeProfile.limitations?.trim()
    ? " A megadott korlátozásaidat az edzés kiválasztásakor tartsd szem előtt."
    : "";
  const checkinReason = checkin?.illness
    ? "A jelzett betegségérzet miatt ma a pihenés az elsődleges."
    : checkin?.pain
      ? "A jelzett fájdalom miatt csak fájdalommentes átmozgatás javasolt."
      : fatiguePenalty > 0
        ? ` A mai check-in ${fatiguePenalty} ponttal óvatosabbá tette az ajánlást.`
        : "";
  const decision = {
    ...(base.decision || {}),
    title,
    duration: checkin?.illness ? "0–20 perc" : duration,
    intensity: checkin?.illness
      ? "pihenés"
      : checkin?.pain
        ? "fájdalommentes"
        : base.decision?.intensity,
    rationale: `${base.decision?.rationale || "A regenerációs jelek alapján."}${checkinReason} ${goalReason}${limitationNote}`,
  };
  const insights = [
    `${actualMinutes} perc készült el a heti ${targetMinutes} perces személyes keretedből.`,
    actualStrength < safeProfile.strengthRatio
      ? `Az erőedzés aránya ${actualStrength}%; a célod ${safeProfile.strengthRatio}%, ezért a következő terhelhető napon érdemes erőblokkot választani.`
      : `Az erő–kardió arányod illeszkedik a ${safeProfile.strengthRatio}/${100 - safeProfile.strengthRatio}%-os célhoz.`,
    safeProfile.eventName && safeProfile.eventDate
      ? `${safeProfile.eventName}: ${Math.max(0, Math.ceil((new Date(safeProfile.eventDate) - new Date()) / 86400000))} nap van hátra.`
      : `A következő ajánlások fő fókusza: ${mode.focus}.`,
  ];
  return {
    decision,
    adjustedReadiness,
    band:
      adjustedReadiness >= 70
        ? "terhelhető"
        : adjustedReadiness >= 45
          ? "óvatosan"
          : "regeneráció",
    week: {
      actualMinutes,
      targetMinutes,
      progress,
      actualStrength,
      targetStrength: safeProfile.strengthRatio,
      daysDone: new Set(recent.map((x) => x.date)).size,
      daysTarget: available,
      totalLoad: week.total_load || 0,
    },
    insights,
  };
}
const dayCodes = ["V", "H", "K", "Sze", "Cs", "P", "Szo"];
const isoDate = (date) => {
  const local = new Date(date);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  return local.toISOString().slice(0, 10);
};
function buildPersonalWeek(profile, data) {
  const anchor = new Date(`${data?.today || isoDate(new Date())}T12:00:00`),
    monday = new Date(anchor);
  monday.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
  const available = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + index);
    return { date, code: dayCodes[date.getDay()] };
  }).filter(
    (day) =>
      profile.trainingDays.includes(day.code) && day.code !== profile.restDay,
  );
  const total = Math.max(60, Number(profile.weeklyHours || 8) * 60),
    count = Math.max(1, available.length),
    strengthCount = Math.min(
      count,
      Math.round((count * Number(profile.strengthRatio || 0)) / 100),
    );
  const strengthSlots = new Set(
    Array.from({ length: strengthCount }, (_, i) =>
      Math.min(
        count - 1,
        Math.round(((i + 0.5) * count) / Math.max(1, strengthCount) - 0.5),
      ),
    ),
  );
  const base = Math.floor(total / count / 5) * 5,
    remainder = total - base * count;
  return available.map((day, index) => {
    const strength = strengthSlots.has(index),
      duration = base + (index === count - 1 ? remainder : 0),
      quality = index === Math.floor(count / 2) && !strength;
    const cardioTitle =
      profile.goal === "Hegyi állóképesség"
        ? quality
          ? "Emelkedős tempó"
          : "Hegyi alapállóképesség"
        : profile.goal === "Futóteljesítmény"
          ? quality
            ? "Tempófutás"
            : "Zone 2 futás"
          : profile.goal === "Általános egészség"
            ? "Könnyű aerob edzés"
            : quality
              ? "Minőségi kardió"
              : "Zone 2 alapozás";
    return {
      date: isoDate(day.date),
      type: strength ? "Erő" : "Kardió",
      title: strength
        ? profile.goal === "Erőfejlesztés" && quality
          ? "Progresszív erőedzés"
          : "Teljes testes erő"
        : cardioTitle,
      duration,
      intensity: quality ? "közepes–magas" : "könnyű–közepes",
      rpe: quality ? 7 : 5,
      purpose: `${profile.goal} · ${strength ? "erőkomponens" : "állóképességi komponens"}`,
      status: "planned",
    };
  });
}
function buildGoalReadiness(data, profile) {
  const sessions = data?.sessions || [],
    cutoff = new Date(`${data?.today || isoDate(new Date())}T12:00:00`);
  cutoff.setDate(cutoff.getDate() - 27);
  const recent = sessions.filter((item) => new Date(item.date) >= cutoff),
    view = personalizeDashboard(data, profile),
    strength = recent.filter((item) => item.type === "Erő").length,
    cardio = recent.filter((item) =>
      ["Futás", "Túrázás", "Kerékpár"].includes(item.type),
    ),
    longest = recent.reduce(
      (max, item) => Math.max(max, Number(item.durationMin || 0)),
      0,
    ),
    actualStrength = recent.length ? (strength / recent.length) * 100 : 0,
    consistency = Math.min(
      100,
      (recent.length / Math.max(8, (profile.trainingDays?.length || 4) * 4)) *
        100,
    ),
    timeFit = Math.min(100, view.week.progress),
    balance = Math.max(
      0,
      100 - Math.abs(actualStrength - profile.strengthRatio) * 2,
    ),
    recovery = Math.min(100, Number(data?.readiness || 0)),
    specific =
      profile.goal === "Erőfejlesztés"
        ? Math.min(100, (strength / 8) * 100)
        : profile.goal === "Hegyi állóképesség"
          ? Math.min(
              100,
              (cardio.filter((item) => item.type === "Túrázás").length +
                longest / 90) *
                25,
            )
          : Math.min(100, (cardio.length + longest / 60) * 12),
    components = [
      ["Következetesség", consistency],
      ["Heti keret", timeFit],
      ["Erő–kardió egyensúly", balance],
      ["Regeneráció", recovery],
      ["Célspecifikusság", specific],
    ],
    score = Math.round(
      components.reduce((sum, [, value]) => sum + value, 0) / components.length,
    ),
    gaps = [];
  if (consistency < 60)
    gaps.push("kevés következetesen rögzített edzés az elmúlt 28 napban");
  if (timeFit < 70) gaps.push("a heti időkeret teljesítése elmarad a céltól");
  if (balance < 65) gaps.push("az erő–kardió arány eltér a személyes célodtól");
  if (recovery < 60)
    gaps.push("a regeneráció jelenleg korlátozza a terhelhetőséget");
  if (specific < 60)
    gaps.push(`kevés ${profile.goal.toLowerCase()}-specifikus edzés`);
  const eventDays = profile.eventDate
    ? Math.ceil((new Date(profile.eventDate) - new Date()) / 86400000)
    : null;
  return {
    score,
    components: components.map(([name, value]) => ({
      name,
      score: Math.round(value),
    })),
    gaps: gaps.length
      ? gaps
      : ["nincs kiemelt hiány a jelenlegi adatok alapján"],
    recentCount: recent.length,
    longest,
    eventDays,
  };
}

const periodizationFocus = {
  "Hibrid teljesítmény": {
    cardio: "Zone 2 és tempó",
    strength: "teljes testes erő",
    key: "Hibrid kulcsedzés",
  },
  Futóteljesítmény: {
    cardio: "Futás",
    strength: "futást támogató erő",
    key: "Minőségi futóedzés",
  },
  Erőfejlesztés: {
    cardio: "Regeneráló kardió",
    strength: "progresszív erő",
    key: "Fő erőedzés",
  },
  "Hegyi állóképesség": {
    cardio: "Emelkedős túra/futás",
    strength: "alsótest és stabilitás",
    key: "Hosszú hegyi nap",
  },
  "Általános egészség": {
    cardio: "Könnyű aerob munka",
    strength: "teljes testes erő",
    key: "Kiegyensúlyozott edzés",
  },
};
function buildPeriodizedCycle(profile, data, weeks) {
  const today = new Date(`${data?.today || isoDate(new Date())}T12:00:00`),
    nextMonday = new Date(today);
  nextMonday.setDate(today.getDate() + ((8 - today.getDay()) % 7 || 7));
  const eventDate = profile.eventDate
      ? new Date(`${profile.eventDate}T12:00:00`)
      : null,
    endMonday = eventDate && eventDate > today ? new Date(eventDate) : null;
  if (endMonday)
    endMonday.setDate(eventDate.getDate() - ((eventDate.getDay() + 6) % 7));
  const eventStart = endMonday ? new Date(endMonday) : null;
  if (eventStart) eventStart.setDate(endMonday.getDate() - (weeks - 1) * 7);
  const start =
      eventStart && eventStart >= nextMonday ? eventStart : nextMonday,
    available = Array.from({ length: 7 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return { offset: index, code: dayCodes[date.getDay()] };
    }).filter(
      (day) =>
        profile.trainingDays.includes(day.code) && day.code !== profile.restDay,
    ),
    focus =
      periodizationFocus[profile.goal] ||
      periodizationFocus["Hibrid teljesítmény"],
    totalMinutes = Number(profile.weeklyHours || 8) * 60;
  return Array.from({ length: weeks }, (_, weekIndex) => {
    const progress = (weekIndex + 1) / weeks,
      last = weekIndex === weeks - 1,
      deload = !last && (weekIndex + 1) % 4 === 0,
      phase =
        last && profile.eventDate
          ? "Eseményhét"
          : last
            ? "Levezetés"
            : deload
              ? "Tehermentesítés"
              : progress <= 0.35
                ? "Alapozás"
                : progress <= 0.75
                  ? "Építés"
                  : "Csúcsforma",
      volume = last
        ? 55
        : deload
          ? 72
          : phase === "Alapozás"
            ? 82 + weekIndex * 3
            : phase === "Építés"
              ? 94 + Math.min(10, weekIndex * 2)
              : 90,
      weekMinutes = Math.round((totalMinutes * volume) / 100 / 5) * 5,
      count = Math.max(1, available.length),
      strengthCount = Math.round(
        (count * Number(profile.strengthRatio || 0)) / 100,
      ),
      weekStart = new Date(start);
    weekStart.setDate(start.getDate() + weekIndex * 7);
    const sessions = available.map((day, index) => {
      const date = new Date(weekStart);
      date.setDate(weekStart.getDate() + day.offset);
      const strength = index < strengthCount,
        key = index === count - 1 && !strength,
        duration = Math.max(
          20,
          Math.round(
            ((weekMinutes / count) * (key ? 1.25 : strength ? 1 : 0.85)) / 5,
          ) * 5,
        ),
        intensity = last
          ? "könnyű"
          : deload
            ? "könnyű–közepes"
            : key && phase !== "Alapozás"
              ? "közepes–magas"
              : "közepes",
        rpe = last ? 4 : deload ? 5 : key ? 7 : 6,
        title = strength
          ? `${focus.strength} · ${phase}`
          : key
            ? `${focus.key} · ${phase}`
            : `${focus.cardio} · ${phase}`;
      return {
        id: `period-${isoDate(date)}`,
        date: isoDate(date),
        type: strength ? "Erő" : "Kardió",
        title,
        duration,
        intensity,
        rpe,
        purpose: `${profile.goal} · ${phase.toLowerCase()} fázis`,
        note: `A ${weeks} hetes ciklus ${weekIndex + 1}. hete · ${volume}% heti volumen`,
        status: "planned",
      };
    });
    return {
      index: weekIndex + 1,
      phase,
      volume,
      weekStart: isoDate(weekStart),
      minutes: sessions.reduce((sum, item) => sum + item.duration, 0),
      focus: last && profile.eventName ? profile.eventName : focus.key,
      sessions,
    };
  });
}

function buildAdaptiveWeek(profile, data, cloudState) {
  const todayValue = data?.today || isoDate(new Date()),
    today = new Date(`${todayValue}T12:00:00`),
    nextMonday = new Date(today);
  nextMonday.setDate(today.getDate() + ((8 - today.getDay()) % 7 || 7));
  const nextEnd = new Date(nextMonday);
  nextEnd.setDate(nextMonday.getDate() + 6);
  const plans = cloudState?.plans || [],
    nextPlans = plans.filter(
      (item) =>
        item.date >= isoDate(nextMonday) && item.date <= isoDate(nextEnd),
    ),
    base = nextPlans.length
      ? nextPlans
      : buildPeriodizedCycle(profile, data, 4)[0].sessions,
    pastStart = new Date(today);
  pastStart.setDate(today.getDate() - 6);
  const recentPlans = plans.filter(
      (item) => item.date >= isoDate(pastStart) && item.date <= todayValue,
    ),
    activities = data?.sessions || [],
    evaluated = recentPlans.map((plan) =>
      evaluatePlan(plan, activities, todayValue),
    ),
    completed = evaluated.filter((item) =>
      ["teljesült", "túlteljesült", "részben teljesült"].includes(item.status),
    ).length,
    missed = evaluated.filter((item) => item.status === "elmaradt").length,
    adherence = recentPlans.length
      ? Math.round((completed / recentPlans.length) * 100)
      : null,
    checkinEntries = Object.entries(cloudState?.checkins || {})
      .filter(([date]) => date <= todayValue)
      .sort(([a], [b]) => b.localeCompare(a)),
    checkin = checkinEntries[0]?.[1],
    readiness = Number(data?.readiness ?? 70),
    reasons = [];
  let adjustment = 0;
  if (checkin?.illness) {
    adjustment -= 35;
    reasons.push(
      "A legutóbbi check-in betegségérzetet jelez, ezért csak regeneráló terhelés marad.",
    );
  } else if (checkin?.pain) {
    adjustment -= 30;
    reasons.push(
      "A jelzett fájdalom miatt a következő hét intenzitása és volumene is csökken.",
    );
  }
  if (readiness < 55) {
    adjustment -= 20;
    reasons.push(
      `A terhelhetőségi érték ${readiness}/100, ezért most a regeneráció élvez elsőbbséget.`,
    );
  } else if (readiness < 70) {
    adjustment -= 10;
    reasons.push(
      `A terhelhetőségi érték ${readiness}/100, ezért kisebb edzésmennyiség javasolt.`,
    );
  }
  if (Number(checkin?.fatigue || 0) >= 4 || Number(checkin?.stress || 0) >= 4) {
    adjustment -= 10;
    reasons.push(
      "A magas fáradtság vagy stressz indokolja a terhelés mérséklését.",
    );
  }
  if (missed >= 2) {
    adjustment -= 10;
    reasons.push(
      `${missed} edzés elmaradt; ezeket nem pótoljuk be sűrítéssel.`,
    );
  } else if (adherence !== null && adherence >= 80 && readiness >= 75) {
    adjustment += 5;
    reasons.push(
      `A ${adherence}%-os tervkövetés és a jó terhelhetőség kis, fokozatos emelést tesz lehetővé.`,
    );
  }
  adjustment = Math.max(-35, Math.min(5, adjustment));
  if (!reasons.length)
    reasons.push(
      "A rendelkezésre álló jelek alapján a következő hét változtatás nélkül folytatható.",
    );
  const factor = (100 + adjustment) / 100,
    adapted = base.map((item) => ({
      ...item,
      id: item.id || `adaptive-${item.date}`,
      duration: Math.max(
        20,
        Math.round((Number(item.duration || 45) * factor) / 5) * 5,
      ),
      intensity:
        adjustment <= -20
          ? "könnyű"
          : adjustment < 0 &&
              ["magas", "közepes–magas"].includes(item.intensity)
            ? "közepes"
            : item.intensity,
      rpe:
        adjustment <= -20
          ? Math.min(5, Number(item.rpe || 5))
          : adjustment < 0
            ? Math.min(6, Number(item.rpe || 6))
            : item.rpe,
      note: `${item.note || ""}${item.note ? " · " : ""}Adaptív heti módosítás: ${adjustment > 0 ? "+" : ""}${adjustment}%`,
      status: "planned",
    }));
  return {
    adapted,
    base,
    adjustment,
    reasons,
    adherence,
    missed,
    readiness,
    checkinDate: checkinEntries[0]?.[0] || null,
    start: isoDate(nextMonday),
    end: isoDate(nextEnd),
  };
}

function BrandMark({ className = "" }) {
  return (
    <img
      className={`brand-mark ${className}`}
      src={brandMarkUrl}
      alt=""
      aria-hidden="true"
    />
  );
}
function BrandLogo({ compact = false }) {
  return (
    <div
      className={`brand-logo ${compact ? "compact" : ""}`}
      aria-label="Hybrid Athlete"
    >
      <span className="brand-logo-mark">
        <BrandMark />
      </span>
      {!compact && (
        <span className="brand-logo-copy">
          <strong>HYBRID ATHLETE</strong>
          <small>SZEMÉLYES EDZÉSDÖNTÉS</small>
        </span>
      )}
    </div>
  );
}
function AnimatedBrandMark({ mode = "running", className = "" }) {
  const assembling = mode === "assembling";
  return (
    <svg
      className={`animated-brand-mark ${assembling ? "assembling" : "running"} ${className}`}
      viewBox={assembling ? "0 0 40 30" : "-30 0 76 34"}
      role="img"
      aria-label={
        assembling
          ? "A Hybrid Athlete logó összeáll"
          : "A Hybrid Athlete szinkronizál"
      }
    >
      {!assembling && (
        <>
          <g
            className="ha-wind ha-wind-teal"
            stroke="var(--accent)"
            strokeLinecap="round"
            fill="none"
          >
            <path d="M-4 7.5 H6" strokeWidth="2.4" opacity=".85" />
            <path d="M-8 12 H4" strokeWidth="2.8" />
            <path d="M-6 16.5 H8" strokeWidth="2.2" opacity=".7" />
            <path d="M-10 21 H2" strokeWidth="2.6" opacity=".9" />
            <path d="M-4 25.5 H6" strokeWidth="2" opacity=".55" />
          </g>
          <g
            className="ha-wind ha-wind-white"
            stroke="rgba(255,255,255,.55)"
            strokeLinecap="round"
            fill="none"
          >
            <path d="M-2 10 H5" strokeWidth="1.1" />
            <path d="M-5 19 H3" strokeWidth="1.1" />
          </g>
        </>
      )}
      <g className={assembling ? "ha-assemble-body" : "ha-run-body"}>
        <path
          className={assembling ? "ha-asm-left" : "ha-run-leg-a"}
          d="M11 28 L16 2 H21 L16 28 Z"
          fill="currentColor"
        />
        <path
          className={assembling ? "ha-asm-right" : "ha-run-leg-b"}
          d="M28 28 L33 2 H38 L33 28 Z"
          fill="currentColor"
        />
        <path
          className={assembling ? "ha-asm-bar" : "ha-run-bar"}
          d="M15.6 18.6 L33.4 9.4 L34.8 14.6 L17 23.8 Z"
          fill="var(--accent)"
        />
        <rect
          className={assembling ? "ha-asm-dash-1" : ""}
          x="0"
          y="9.6"
          width="9"
          height="3.4"
          rx="1.7"
          fill="var(--accent)"
          opacity={assembling ? undefined : ".55"}
        />
        <rect
          className={assembling ? "ha-asm-dash-2" : ""}
          x="4"
          y="16.4"
          width="6"
          height="3.4"
          rx="1.7"
          fill="var(--accent)"
          opacity={assembling ? undefined : ".3"}
        />
      </g>
      {!assembling && (
        <g
          className="ha-ground"
          stroke="rgba(255,255,255,.16)"
          strokeWidth="1.4"
          strokeLinecap="round"
        >
          <path d="M6 31 H18" />
          <path d="M28 31 H40" />
          <path d="M50 31 H62" />
          <path d="M72 31 H84" />
        </g>
      )}
    </svg>
  );
}
function BrandSplash({ onDone }) {
  useEffect(() => {
    const reduce = window.matchMedia?.(
        "(prefers-reduced-motion: reduce)",
      ).matches,
      timer = setTimeout(onDone, reduce ? 250 : 4200);
    return () => clearTimeout(timer);
  }, [onDone]);
  return (
    <div className="brand-splash" role="status" aria-live="polite">
      <div className="brand-splash-lockup">
        <AnimatedBrandMark mode="assembling" />
        <strong>HYBRID ATHLETE</strong>
        <span>SZEMÉLYES EDZÉSDÖNTÉS</span>
      </div>
    </div>
  );
}
const splashWasShown = () =>
  globalThis.sessionStorage?.getItem("hybrid-splash-shown") === "1";
const forceSplashPreview = () =>
  new URLSearchParams(globalThis.window?.location?.search || "").get(
    "splash",
  ) === "1";
const avatarPresets = {
  athlete: Activity,
  strength: Dumbbell,
  endurance: TrendingUp,
  classic: UserRound,
};
function AvatarView({ profile, size = "normal" }) {
  const initials = (profile?.name || "A")
      .split(/\s+/)
      .map((x) => x[0])
      .join("")
      .slice(0, 2)
      .toUpperCase(),
    Icon = avatarPresets[profile?.avatarPreset] || UserRound;
  return (
    <span className={`user-avatar ${size}`}>
      {profile?.avatarImage ? (
        <img
          src={profile.avatarImage}
          alt={`${profile.name || "Felhasználó"} profilképe`}
        />
      ) : profile?.avatarPreset ? (
        <Icon aria-hidden="true" />
      ) : (
        <b>{initials}</b>
      )}
    </span>
  );
}
function Sidebar({ collapsed, onToggle, active, onActive, profile, garminStatus }) {
  const initials = (profile?.name || "Attila")
    .split(/\s+/)
    .map((x) => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <aside className={collapsed ? "sidebar collapsed" : "sidebar"}>
      <div className="brand">
        <BrandLogo compact={collapsed} />
      </div>
      <nav>
        {nav.map(([label, Icon]) => (
          <button
            className={active === label ? "active" : ""}
            onClick={() => onActive(label)}
            key={label}
          >
            <Icon size={16} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="side-bottom">
        <button>
          <HelpCircle size={16} />
          <span>Súgó</span>
        </button>
        <button onClick={() => onActive("Beállítások")}>
          <Settings2 size={16} />
          <span>Beállítások</span>
        </button>
        <div className="profile">
          <AvatarView profile={profile} size="small" />
          <div>
            <b>{profile?.name || "Attila"}</b>
            <small>{garminStatus?.status === "connected" ? "Garmin csatlakoztatva" : "Garmin nincs összekötve"}</small>
          </div>
        </div>
      </div>
      <button className="collapse" onClick={onToggle}>
        {collapsed ? <Menu size={17} /> : <ChevronLeft size={17} />}
      </button>
    </aside>
  );
}

function Heatmap({ values = heat }) {
  return (
    <div className="heatmap" aria-label="12 hetes terhelési hőtérkép">
      {values.map((v, i) => (
        <i key={i} data-level={v} />
      ))}
    </div>
  );
}

const emptyCheckin = {
  soreness: 2,
  fatigue: 2,
  motivation: 4,
  stress: 2,
  pain: false,
  illness: false,
  note: "",
};
function CheckIn({ value, onSave, required = false }) {
  const [values, setValues] = useState(value || emptyCheckin),
    [saved, setSaved] = useState(Boolean(value?.savedAt)),
    [answered, setAnswered] = useState(
      () =>
        new Set(
          value?.savedAt ? ["soreness", "fatigue", "motivation", "stress"] : [],
        ),
    );
  useEffect(() => {
    setValues(value || emptyCheckin);
    setSaved(Boolean(value?.savedAt));
    setAnswered(
      new Set(
        value?.savedAt ? ["soreness", "fatigue", "motivation", "stress"] : [],
      ),
    );
  }, [value]);
  const set = (key, next) => {
      setValues((current) => ({ ...current, [key]: next }));
      setSaved(false);
      if (["soreness", "fatigue", "motivation", "stress"].includes(key))
        setAnswered((current) => new Set([...current, key]));
    },
    row = (key, label) => (
      <div className="scale-row">
        <span>{label}</span>
        <div>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              className={
                answered.has(key) && values[key] === n ? "selected" : ""
              }
              onClick={() => set(key, n)}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    ),
    complete = answered.size === 4;
  return (
    <section
      className={`card checkin ${required && !saved ? "checkin-required" : ""}`}
    >
      <div className="section-head">
        <div>
          <span className="eyebrow">GYORS ÁLLAPOTFELMÉRÉS</span>
          <p>
            {required && !saved
              ? "Válaszolj mind a négy kérdésre, hogy a Garmin-adatokkal együtt személyes javaslatot készíthessünk."
              : "Adj rövid kontextust a mai döntéshez."}
          </p>
        </div>
        <small>
          {saved
            ? `MENTVE · ${new Date(values.savedAt).toLocaleTimeString("hu-HU", { hour: "2-digit", minute: "2-digit" })}`
            : `${answered.size} / 4 KITÖLTVE`}
        </small>
      </div>
      <div className="check-grid">
        {row("soreness", "Izomláz")}
        {row("fatigue", "Fáradtság")}
        {row("motivation", "Motiváció")}
        {row("stress", "Stressz")}
      </div>
      <div className="check-alerts">
        <button
          className={values.pain ? "selected" : ""}
          onClick={() => set("pain", !values.pain)}
        >
          Fájdalmat érzek
        </button>
        <button
          className={values.illness ? "selected" : ""}
          onClick={() => set("illness", !values.illness)}
        >
          Betegségérzetem van
        </button>
      </div>
      <div className="check-footer">
        <input
          value={values.note}
          onChange={(event) => set("note", event.target.value)}
          placeholder="Megjegyzés (nem kötelező)"
        />
        <button
          disabled={required && !complete}
          onClick={() => {
            const next = { ...values, savedAt: new Date().toISOString() };
            setValues(next);
            setSaved(true);
            onSave(next);
          }}
        >
          {saved ? "Elmentve" : "Mentés és a javaslat kiszámítása"}
        </button>
      </div>
    </section>
  );
}

function Decision({ onWhy, data, profile, checkin }) {
  const view = personalizeDashboard(data, profile, checkin),
    score = view.adjustedReadiness;
  const radial = [
      { name: "terhelhetőség", value: score, fill: "var(--accent)" },
    ],
    d = view.decision;
  return (
    <section className="card decision-card">
      <div className="decision-main">
        <div className="ring">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              innerRadius="82%"
              outerRadius="100%"
              data={radial}
              startAngle={90}
              endAngle={-270}
            >
              <PolarAngleAxis
                type="number"
                domain={[0, 100]}
                angleAxisId={0}
                tick={false}
              />
              <RadialBar
                dataKey="value"
                cornerRadius={8}
                background={{ fill: "#292929" }}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <strong>{score}</strong>
        </div>
        <div className="decision-copy">
          <div className="recommend">
            <MetricHelp term="Readiness">
              <span>{view.band.toUpperCase()}</span>
            </MetricHelp>
            <MetricHelp term="Bizonyosság">
              <small>
                {(data?.confidence || "MAGAS").toUpperCase()} BIZONYOSSÁG
              </small>
            </MetricHelp>
          </div>
          <h2>{d.title}</h2>
          <p>{`${d.duration} · ${d.intensity || "személyre szabott intenzitás"}`}</p>
          <div className="decision-note">
            <b>Miért ezt?</b>
            <span>{d.rationale}</span>
          </div>
        </div>
      </div>
      <button className="why" onClick={onWhy}>
        MIÉRT EZT AJÁNLOD? <ChevronDown size={15} />
      </button>
    </section>
  );
}

function metricImpact(name, score) {
  const level =
    score >= 75
      ? "kedvező"
      : score >= 55
        ? "elfogadható"
        : "óvatosságot indokol";
  if (name.includes("HRV"))
    return `A személyes alapértékedhez viszonyított állapot ${level}. Tartós romlásnál érdemes csökkenteni az intenzitást.`;
  if (name.includes("Alvás"))
    return `Az alvásból számolt regeneráció ${level}. Gyengébb értéknél a technika és a könnyebb aerob munka biztonságosabb választás.`;
  if (name.includes("pulzus"))
    return `A nyugalmi pulzusból származó jel ${level}. Szokatlan emelkedés esetén figyeld a fáradtságot és a betegségérzetet.`;
  return `A rövid és hosszú távú terhelés egyensúlya ${level}. Negatívabb állapot több pihenést, pozitívabb állapot nagyobb frissességet jelezhet.`;
}
function ReadinessMetric({ row, data }) {
  const [name, value, delta, width, tone] = row,
    [open, setOpen] = useState(false),
    quality =
      data?.source === "garmin"
        ? `${(data?.confidence || "közepes").toLowerCase()} bizonyosságú Garmin-adat`
        : "bemutató adat – saját szinkron után válik személyessé",
    term = name.includes("TSB") ? "TSB" : name;
  return (
    <div className={`metric-wrap ${open ? "open" : ""}`}>
      <button
        className="metric"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className={`metric-icon ${tone}`}>
          <Activity size={15} />
        </span>
        <b>{name}</b>
        <strong>{value}</strong>
        <span
          className="bar"
          aria-label={`${name} hozzájárulási pontszáma: ${Math.round(width)} / 100`}
        >
          <i style={{ width: `${Math.max(0, Math.min(100, width))}%` }} />
        </span>
        <em>{delta}</em>
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="metric-detail">
          <div>
            <span>MIT JELENT MOST?</span>
            <p>{metricImpact(name, width)}</p>
          </div>
          <div>
            <span>ADATMINŐSÉG</span>
            <p>
              {quality}. A sáv a terhelhetőséghez való 0–100-as kedvező
              hozzájárulást mutatja, nem önálló egészségügyi minősítés.
            </p>
          </div>
          <div>
            <span>GYAKORLATI KÖVETKEZMÉNY</span>
            <p>
              {width < 55
                ? "A mai tervben válassz kisebb intenzitást, és a saját közérzeted legyen az elsődleges."
                : width < 75
                  ? "Az edzés elvégezhető, de ne növeld egyszerre az időtartamot és az intenzitást."
                  : "Ez a jel jelenleg nem korlátozza érdemben a terhelést, ha a többi összetevő és a közérzeted is rendben van."}
            </p>
          </div>
          <MetricHelp term={term}>Részletes fogalommagyarázat</MetricHelp>
        </div>
      )}
    </div>
  );
}
function MetricList({ data }) {
  const rows = data?.metrics?.length
    ? data.metrics.map((x) => [
        x.name,
        x.value,
        "",
        x.score,
        x.name.startsWith("HRV") ? "warn" : "good",
      ])
    : metrics;
  return (
    <section className="card metric-card">
      <div className="section-head">
        <MetricHelp term="Readiness">
          <span className="eyebrow">TERHELHETŐSÉG ÖSSZETEVŐI</span>
        </MetricHelp>
        <small>
          {data?.source === "garmin"
            ? `${rows.length} MÉRŐSZÁM · ${(data?.confidence || "KÖZEPES").toUpperCase()} BIZONYOSSÁG`
            : `${rows.length} DEMO MÉRŐSZÁM`}
        </small>
      </div>
      {rows.map((row) => (
        <ReadinessMetric key={row[0]} row={row} data={data} />
      ))}
    </section>
  );
}

function Today() {
  const [whyOpen, setWhyOpen] = useState(false);
  return (
    <>
      <header>
        <div>
          <span className="eyebrow">PÉNTEK · AUGUSZTUS 14.</span>
          <h1>A mai döntés</h1>
        </div>
        <div className="header-actions">
          <span>UTOLSÓ SZINKRON · 2 PERCE</span>
          <button>
            <RefreshCw size={14} /> SZINKRON
          </button>
          <button aria-label="Téma">
            <Moon size={15} />
          </button>
        </div>
      </header>
      <main className="dashboard">
        <div className="left">
          <Decision onWhy={() => setWhyOpen(true)} />
          <CheckIn />
          <MetricList />
        </div>
        <div className="right">
          <section className="card load-card">
            <div className="section-head">
              <span className="eyebrow">TERHELÉS · 12 HÉT</span>
              <small>CTL 42 · ATL 31</small>
            </div>
            <Heatmap />
            <div className="heat-legend">
              <span>KEVESEBB</span>
              <i data-level="1" />
              <i data-level="2" />
              <i data-level="3" />
              <span>TÖBB</span>
            </div>
          </section>
          <section className="card week">
            <div className="section-head">
              <span className="eyebrow">HETI KERET</span>
              <small>5 / 7 NAP</small>
            </div>
            <div className="weekbar">
              <i />
            </div>
            <div className="week-stats">
              <div>
                <strong>24 480</strong>
                <span>TERHELÉS</span>
              </div>
              <div>
                <strong>16ó 30p</strong>
                <span>EDZÉSIDŐ</span>
              </div>
              <div>
                <strong>25%</strong>
                <span>ERŐ ARÁNY</span>
              </div>
            </div>
            <p>
              Most a terv közepén jársz. A mai könnyű aerob blokk támogatja a
              heti egyensúlyt.
            </p>
          </section>
          <section className="card insights">
            <div className="section-head">
              <span className="eyebrow">AZ ELMÚLT 30 NAP</span>
              <small>4 JELZÉS</small>
            </div>
            {[
              "A Z2 futások után stabilabb a következő napi HRV-d.",
              "Két egymást követő erőedzés után hosszabb regeneráció kell.",
              "A 7 óra feletti alvás javítja a másnapi terhelhetőséget.",
            ].map((x, i) => (
              <div className="insight" key={x}>
                <Sparkles size={14} />
                <span>{x}</span>
                <i className={i === 1 ? "amber" : ""} />
              </div>
            ))}
          </section>
        </div>
      </main>
      {whyOpen && (
        <div className="modal-backdrop" onClick={() => setWhyOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="close" onClick={() => setWhyOpen(false)}>
              <X size={18} />
            </button>
            <span className="eyebrow">AZ AJÁNLÁS HÁTTERE</span>
            <h2>Miért Z2 futás?</h2>
            <p>
              A readiness 78/100, a HRV a személyes alapérték felett van, az
              alvásod megfelelő, és a rövid távú terhelés nem lépte át az
              óvatossági tartományt.
            </p>
            <ul>
              <li>HRV: stabil, pozitív eltérés</li>
              <li>Alvás: 7 óra 12 perc</li>
              <li>TSB: +4,2, friss állapot</li>
            </ul>
            <button className="primary" onClick={() => setWhyOpen(false)}>
              Értem
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function TodayLive({
  profile,
  cloudState,
  onCloudPatch,
  garminStatus,
  onConnect,
}) {
  const [data, setData] = useState(null),
    [syncing, setSyncing] = useState(false),
    [syncJob, setSyncJob] = useState(null),
    [error, setError] = useState(""),
    [whyOpen, setWhyOpen] = useState(false),
    [checkin, setCheckin] = useState(null);
  const load = () =>
    fetch("/api/dashboard")
      .then(async (r) => {
        const text = await r.text();
        let body = null;
        try {
          body = JSON.parse(text);
        } catch {
          throw new Error(
            "A helyi Garmin API nem érhető el; a beépített mintaadatok láthatók.",
          );
        }
        if (!r.ok)
          throw new Error(body?.error || "Az adatok nem tölthetők be.");
        return body;
      })
      .then((value) => {
        setData(value);
        setError("");
      })
      .catch((e) => setError(e.message || "Az adatok nem tölthetők be."));
  useEffect(() => {
    load();
  }, []);
  const syncNow = async (initialRunId = null) => {
    setSyncing(true);
    setError("");
    let runId = initialRunId;
    try {
      for (let step = 0; step < 20000; step += 1) {
        const r = await fetch("/api/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(runId ? { run_id: runId } : {}),
          }),
          text = await r.text();
        let body = null;
        try {
          body = JSON.parse(text);
        } catch {
          if (r.status === 404 || /page could not be found|doctype/i.test(text))
            throw new Error(
              "Az online Garmin-szinkron még nincs bekötve ezen az előnézeten.",
            );
          const reference = text.trim().slice(0, 120);
          throw new Error(
            `A szinkronizáló szolgáltatás nem JSON választ adott (${r.status})${reference ? `: ${reference}` : "."}`,
          );
        }
        if (!r.ok && r.status !== 202)
          throw new Error(
            body?.error ||
              body?.message ||
              `A szinkron nem sikerült (${r.status}).`,
          );
        setSyncJob(body);
        runId = body.run_id;
        if (body.status === "completed") {
          await load();
          break;
        }
        if (body.status === "failed")
          throw new Error(body.message || "A szinkron megszakadt.");
        await new Promise((resolve) => setTimeout(resolve, 350));
      }
    } catch (e) {
      setError(e.message || "A szinkron nem sikerült.");
    } finally {
      setSyncing(false);
    }
  };
  useEffect(() => {
    fetch("/api/sync")
      .then((r) => (r.ok ? r.json() : null))
      .then((job) => {
        if (job?.status === "running") {
          setSyncJob(job);
          syncNow(job.run_id);
        } else if (job) setSyncJob(job);
      })
      .catch(() => {});
  }, []);
  const checkinKey = data?.today || isoDate(new Date());
  useEffect(() => {
    const cloud = cloudState?.checkins?.[checkinKey];
    if (cloud) {
      setCheckin(cloud);
      localStorage.setItem(
        `hybrid-checkin-${checkinKey}`,
        JSON.stringify(cloud),
      );
      return;
    }
    try {
      setCheckin(
        JSON.parse(
          localStorage.getItem(`hybrid-checkin-${checkinKey}`) || "null",
        ),
      );
    } catch {
      setCheckin(null);
    }
  }, [checkinKey, cloudState]);
  const saveCheckin = (value) => {
      localStorage.setItem(
        `hybrid-checkin-${checkinKey}`,
        JSON.stringify(value),
      );
      setCheckin(value);
      onCloudPatch({ checkin: { date: checkinKey, value } });
    },
    stamp = data?.generatedAt
      ? new Date(data.generatedAt).toLocaleTimeString("hu-HU", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "—",
    view = personalizeDashboard(data, profile, checkin),
    week = view.week,
    formatMinutes = (value) =>
      `${Math.floor(value / 60)} óra ${value % 60} perc`;
  if (!checkin?.savedAt)
    return (
      <>
        <header>
          <div>
            <span className="eyebrow">{data?.today || "MA"}</span>
            <h1>Kezdjük a napi állapotfelméréssel</h1>
          </div>
          <div className="header-actions">
            {garminStatus?.status !== "connected" && (
              <button onClick={onConnect}>
                <Activity size={14} /> ÖSSZEKÖTÉS GARMIN-FIÓKKAL
              </button>
            )}
            <button aria-label="Téma">
              <Moon size={15} />
            </button>
          </div>
        </header>
        <main className="checkin-gate">
          <div>
            <span className="eyebrow">A MAI AJÁNLÁS ELSŐ LÉPÉSE</span>
            <h2>Hogyan érzed magad ma?</h2>
            <p>
              A válaszaidat összevetjük a Garminból érkező regenerációs és
              terhelési adatokkal. Az ajánlás csak ezután jelenik meg.
            </p>
          </div>
          <CheckIn value={checkin} onSave={saveCheckin} required />
        </main>
      </>
    );
  return (
    <>
      <header>
        <div>
          <span className="eyebrow">{data?.today || "MA"}</span>
          <h1>A mai döntés</h1>
        </div>
        <div className="header-actions">
          <span>
            {error
              ? error
              : `${data?.source === "garmin" ? "GARMIN" : "DEMO"} · ${stamp}`}
          </span>
          {garminStatus?.status === "connected" ? (
            <button onClick={() => syncNow()} disabled={syncing}>
              {syncing ? (
                <AnimatedBrandMark className="sync-brand-mark" />
              ) : (
                <RefreshCw size={14} />
              )}{" "}
              {syncing
                ? `${Math.round(syncJob?.progress || 0)}%`
                : "SZINKRONIZÁLÁS"}
            </button>
          ) : (
            <button onClick={onConnect}>
              <Activity size={14} /> ÖSSZEKÖTÉS GARMIN-FIÓKKAL
            </button>
          )}
          <button aria-label="Téma">
            <Moon size={15} />
          </button>
        </div>
      </header>
      {syncing && syncJob && (
        <section className="sync-progress" role="status" aria-live="polite">
          <div>
            <AnimatedBrandMark />
            <span>
              <b>Teljes Garmin-előzmény szinkronizálása</b>
              <small>{syncJob.message}</small>
            </span>
            <strong>{Math.round(syncJob.progress || 0)}%</strong>
          </div>
          <progress max="100" value={syncJob.progress || 0} />
          <p>
            Az állapot a Neon adattárban megmarad. Ha bezárod vagy újratöltöd az
            oldalt, a folyamat innen folytatható.
          </p>
        </section>
      )}
      <main className="dashboard">
        <div className="left">
          <Decision
            data={data}
            profile={profile}
            checkin={checkin}
            onWhy={() => setWhyOpen(true)}
          />
          <CheckIn value={checkin} onSave={saveCheckin} />
          <MetricList data={data} />
        </div>
        <div className="right">
          <section className="card load-card">
            <div className="section-head">
              <span className="eyebrow">TERHELÉS · 12 HÉT</span>
              <small>
                {data?.source === "garmin" ? "GARMIN ADAT" : "DEMO ADAT"}
              </small>
            </div>
            <Heatmap values={data?.heat} />
            <div className="heat-legend">
              <span>KEVESEBB</span>
              <i data-level="1" />
              <i data-level="2" />
              <i data-level="3" />
              <span>TÖBB</span>
            </div>
          </section>
          <section className="card week">
            <div className="section-head">
              <span className="eyebrow">HETI KERET</span>
              <small>
                {week.daysDone} / {week.daysTarget} NAP
              </small>
            </div>
            <div className="weekbar">
              <i
                style={{
                  width: `${week.progress}%`,
                  borderRight: week.progress < 100 ? "42px solid #f59e0b" : "0",
                }}
              />
            </div>
            <div className="week-stats">
              <div>
                <strong>{week.totalLoad.toLocaleString("hu-HU")}</strong>
                <span>TERHELÉS</span>
              </div>
              <div>
                <strong>{formatMinutes(week.actualMinutes)}</strong>
                <span>{formatMinutes(week.targetMinutes)} CÉLBÓL</span>
              </div>
              <div>
                <strong>{week.actualStrength}%</strong>
                <span>{week.targetStrength}% ERŐ CÉL</span>
              </div>
            </div>
            <p>
              A heti időkeret {week.progress}%-a teljesült. A mai ajánlás a{" "}
              {profile.goal.toLowerCase()} célodhoz igazodik.
            </p>
          </section>
          <section className="card insights">
            <div className="section-head">
              <span className="eyebrow">SZEMÉLYES JELZÉSEK</span>
              <small>{view.insights.length} AKTÍV</small>
            </div>
            {view.insights.map((x, i) => (
              <div className="insight" key={x}>
                <Sparkles size={14} />
                <span>{x}</span>
                <i className={i === 1 ? "amber" : ""} />
              </div>
            ))}
          </section>
        </div>
      </main>
      {whyOpen && (
        <div className="modal-backdrop" onClick={() => setWhyOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="close" onClick={() => setWhyOpen(false)}>
              <X size={18} />
            </button>
            <span className="eyebrow">SZEMÉLYES AJÁNLÁS</span>
            <h2>Miért {view.decision.title.toLowerCase()}?</h2>
            <p>{view.decision.rationale}</p>
            <ul>
              <li>Garmin alapján: {data?.readiness ?? 78}/100</li>
              <li>Az állapotfelmérés után: {view.adjustedReadiness}/100</li>
              <li>Fő cél: {profile.goal}</li>
              <li>
                Heti keret: {profile.weeklyHours} óra, {profile.strengthRatio}%
                erő
              </li>
              <li>Edzésirány: {profile.preference}</li>
            </ul>
            <button className="primary" onClick={() => setWhyOpen(false)}>
              Értem
            </button>
          </div>
        </div>
      )}
    </>
  );
}

const viewArtwork = {
  "Terv és tény": "naptar",
  "Terhelés és forma": "trendek",
  "Mi működik nálam": "insights",
  Edzések: "naplo",
  Profil: "profil",
  Beállítások: "profil",
  Felkészültség: "trendek",
};
function PageHeader({ eyebrow, title, children }) {
  const artwork = viewArtwork[title] || "ma";
  return (
    <header className={`page-header page-header-${artwork}`}>
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
      </div>
      {children}
    </header>
  );
}

function CalendarPage({ profile }) {
  const data = useDashboardData(),
    anchor = new Date(`${data?.today || isoDate(new Date())}T12:00:00`),
    [month, setMonth] = useState(
      () => new Date(anchor.getFullYear(), anchor.getMonth(), 1),
    ),
    [selected, setSelected] = useState(() => isoDate(anchor)),
    [details, setDetails] = useState(false);
  const plan = buildPersonalWeek(profile, data),
    planned = new Map(plan.map((item) => [item.date, item])),
    actual = new Map(
      (data?.sessions || []).map((item) => [
        item.date,
        {
          ...item,
          title: item.name,
          duration: item.durationMin,
          status: "done",
        },
      ]),
    );
  const first = new Date(month.getFullYear(), month.getMonth(), 1),
    gridStart = new Date(first);
  gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const cells = Array.from({ length: 42 }, (_, index) => {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + index);
      const key = isoDate(date),
        item = actual.get(key) || planned.get(key);
      return { date, key, item, current: date.getMonth() === month.getMonth() };
    }),
    selectedItem = actual.get(selected) || planned.get(selected),
    selectedDate = new Date(`${selected}T12:00:00`),
    monthLabel = month.toLocaleDateString("hu-HU", {
      year: "numeric",
      month: "long",
    });
  const shift = (value) =>
    setMonth(
      (current) =>
        new Date(current.getFullYear(), current.getMonth() + value, 1),
    );
  return (
    <>
      <PageHeader eyebrow="SZEMÉLYES HETI TERV" title="Terv és tény">
        <div className="calendar-actions">
          <button aria-label="Előző hónap" onClick={() => shift(-1)}>
            <ChevronLeft size={14} />
          </button>
          <b>{monthLabel}</b>
          <button aria-label="Következő hónap" onClick={() => shift(1)}>
            <ChevronRight size={14} />
          </button>
        </div>
      </PageHeader>
      <div className="calendar-legend">
        <span>
          <i className="planned" />
          TERVEZETT
        </span>
        <span>
          <i className="done" />
          TELJESÍTETT
        </span>
        <span>
          <i className="extra" />
          GARMIN ELŐZMÉNY
        </span>
      </div>
      <section className="calendar card">
        <div className="weekdays">
          {[
            "HÉTFŐ",
            "KEDD",
            "SZERDA",
            "CSÜTÖRTÖK",
            "PÉNTEK",
            "SZOMBAT",
            "VASÁRNAP",
          ].map((x) => (
            <b key={x}>{x}</b>
          ))}
        </div>
        <div className="calendar-grid">
          {cells.map((cell) => (
            <button
              key={cell.key}
              className={`${cell.key === selected ? "selected" : ""} ${!cell.current ? "outside" : ""}`}
              onClick={() => setSelected(cell.key)}
            >
              <span>{cell.date.getDate()}</span>
              {cell.item && (
                <div className={cell.item.status}>
                  <Activity size={13} />
                  <b>{cell.item.type}</b>
                  <small>
                    {cell.item.title} · {cell.item.duration}p
                  </small>
                </div>
              )}
            </button>
          ))}
        </div>
      </section>
      <div className="calendar-detail card">
        <div>
          <span className="eyebrow">KIVÁLASZTOTT NAP</span>
          <h2>
            {selectedDate.toLocaleDateString("hu-HU", {
              month: "long",
              day: "numeric",
            })}
          </h2>
        </div>
        <p>
          {selectedItem
            ? `${selectedItem.title} · ${selectedItem.duration} perc · ${selectedItem.status === "done" ? "Garmin-adat" : "személyes terv"}`
            : selectedDate.getDay() === 0 ||
                dayCodes[selectedDate.getDay()] === profile.restDay
              ? "Tervezett pihenőnap."
              : "Nincs edzés erre a napra."}
        </p>
        <button disabled={!selectedItem} onClick={() => setDetails(true)}>
          EDZÉS RÉSZLETEI
        </button>
      </div>
      {details && selectedItem && (
        <div className="modal-backdrop" onClick={() => setDetails(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <button className="close" onClick={() => setDetails(false)}>
              <X size={18} />
            </button>
            <span className="eyebrow">
              {selectedItem.status === "done"
                ? "TELJESÍTETT EDZÉS"
                : "SZEMÉLYES HETI TERV"}
            </span>
            <h2>{selectedItem.title}</h2>
            <p>
              {selectedDate.toLocaleDateString("hu-HU", {
                year: "numeric",
                month: "long",
                day: "numeric",
                weekday: "long",
              })}
            </p>
            <ul>
              <li>Időtartam: {selectedItem.duration} perc</li>
              <li>Típus: {selectedItem.type}</li>
              {selectedItem.intensity && (
                <li>Intenzitás: {selectedItem.intensity}</li>
              )}
              {selectedItem.rpe && <li>Cél RPE: {selectedItem.rpe}/10</li>}
              {selectedItem.purpose && <li>Cél: {selectedItem.purpose}</li>}
              {selectedItem.avgHr && (
                <li>Átlagpulzus: {selectedItem.avgHr} bpm</li>
              )}
              {selectedItem.distanceKm > 0 && (
                <li>Táv: {selectedItem.distanceKm} km</li>
              )}
            </ul>
            <button className="primary" onClick={() => setDetails(false)}>
              Rendben
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function TrendsPage() {
  const [range, setRange] = useState("90 nap");
  const zones = [
    { z: "Z1", m: 34, c: "#23766b" },
    { z: "Z2", m: 78, c: "#14b8a6" },
    { z: "Z3", m: 16, c: "#3b82f6" },
    { z: "Z4", m: 20, c: "#f59e0b" },
    { z: "Z5", m: 9, c: "#ef4444" },
  ];
  return (
    <>
      <PageHeader eyebrow="TERHELÉS" title="Terhelés és forma">
        <div className="segmented">
          {["30 nap", "90 nap", "1 év"].map((x) => (
            <button
              key={x}
              className={range === x ? "active" : ""}
              onClick={() => setRange(x)}
            >
              {x}
            </button>
          ))}
        </div>
      </PageHeader>
      <section className="card chart-card">
        <div className="section-head">
          <span className="eyebrow">
            HOSSZÚ TÁVÚ TERHELÉS · ATL · CTL · TSB
          </span>
          <small>{range.toUpperCase()}</small>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trendData}>
            <CartesianGrid stroke="#2a2b2b" vertical={false} />
            <XAxis dataKey="week" stroke="#646766" fontSize={9} />
            <YAxis stroke="#646766" fontSize={9} />
            <Tooltip
              contentStyle={{
                background: "#181a19",
                border: "1px solid #343635",
              }}
            />
            <Line
              type="monotone"
              dataKey="ctl"
              stroke="#14b8a6"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="atl"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="tsb"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </section>
      <div className="trend-bottom">
        <section className="card zone-card">
          <div className="section-head">
            <span className="eyebrow">ZÓNAIDŐ ELOSZLÁS · HÉT</span>
            <small>157 PERC</small>
          </div>
          {zones.map((x) => (
            <div className="zone-row" key={x.z}>
              <b>{x.z}</b>
              <span>
                <i style={{ width: `${x.m}%`, background: x.c }} />
              </span>
              <strong>{x.m}p</strong>
            </div>
          ))}
        </section>
        <section className="card dimensions">
          <div className="section-head">
            <span className="eyebrow">DIMENZIÓK · 90 NAP</span>
            <small>AKTUÁLIS</small>
          </div>
          {[
            ["Kardió", 82, "#14b8a6", "STABIL"],
            ["Erő", 66, "#3b82f6", "EMELKEDŐ"],
            ["Mozgásszervi", 73, "#f59e0b", "MAGAS"],
          ].map(([n, v, c, s]) => (
            <div className="dimension" key={n}>
              <div>
                <b>{n}</b>
                <small>{s}</small>
              </div>
              <span>
                <i style={{ width: `${v}%`, background: c }} />
              </span>
              <strong>{v}</strong>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}

function LiveTrendsPage({ profile }) {
  const data = useDashboardData(),
    [range, setRange] = useState("90 nap"),
    days = range === "30 nap" ? 30 : range === "90 nap" ? 90 : 365,
    limit = range === "30 nap" ? 5 : range === "90 nap" ? 13 : 52,
    rawPoints = (data?.trends || trendData).slice(-limit),
    points = rawPoints.map((x, i) => ({
      ...x,
      week: x.date
        ? new Date(x.date).toLocaleDateString("hu-HU", {
            month: "short",
            day: "numeric",
          })
        : x.week || `${i + 1}. hét`,
    })),
    current = rawPoints.at(-1) || {},
    previous = rawPoints.at(-2) || current,
    delta = (key) =>
      Math.round(
        (Number(current[key] || 0) - Number(previous[key] || 0)) * 10,
      ) / 10;
  const sessions = data?.sessions || [],
    latest = sessions[0]?.date ? new Date(sessions[0].date) : new Date(),
    from = new Date(latest);
  from.setDate(latest.getDate() - days + 1);
  const periodSessions = sessions.filter((item) => new Date(item.date) >= from),
    weeklyFrequency =
      Math.round((periodSessions.length / (days / 7)) * 10) / 10;
  let feedback = {};
  try {
    feedback = JSON.parse(
      localStorage.getItem("hybrid-activity-feedback") || "{}",
    );
  } catch {}
  const rpes = periodSessions
      .map((item) => feedback[item.id]?.rpe)
      .filter(Boolean),
    averageRpe = rpes.length
      ? Math.round(
          (rpes.reduce((sum, value) => sum + value, 0) / rpes.length) * 10,
        ) / 10
      : null,
    zoneValues = data?.zones || [34, 78, 16, 20, 9],
    total = zoneValues.reduce((a, b) => a + b, 0),
    colors = ["#23766b", "var(--accent)", "#3b82f6", "#f59e0b", "#ef4444"],
    eventDays = profile.eventDate
      ? Math.ceil((new Date(profile.eventDate) - new Date()) / 86400000)
      : null;
  const summaries = [
    [Math.round(current.ctl || 0), "CTL", delta("ctl")],
    [Math.round(current.atl || 0), "ATL", delta("atl")],
    [Number(current.tsb || 0).toFixed(1), "TSB", delta("tsb")],
    [weeklyFrequency, "EDZÉS / HÉT", null],
    [averageRpe ?? "—", "ÁTLAG RPE", null],
  ];
  return (
    <>
      <PageHeader
        eyebrow="SZEMÉLYES FEJLŐDÉSTÖRTÉNET"
        title="Terhelés és forma"
      >
        <div className="segmented">
          {["30 nap", "90 nap", "1 év"].map((x) => (
            <button
              key={x}
              className={range === x ? "active" : ""}
              onClick={() => setRange(x)}
            >
              {x}
            </button>
          ))}
        </div>
      </PageHeader>
      <section className="trend-summary">
        {summaries.map(([value, label, change]) => (
          <div className="card" key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
            {change !== null && (
              <small className={change >= 0 ? "up" : "down"}>
                {change >= 0 ? "+" : ""}
                {change} az előző héthez képest
              </small>
            )}
          </div>
        ))}
      </section>
      <section className="card chart-card">
        <div className="section-head">
          <span className="eyebrow">
            HOSSZÚ TÁVÚ TERHELÉS · ATL · CTL · TSB
          </span>
          <small>
            {data?.source === "garmin" ? "GARMIN" : "DEMO"} ·{" "}
            {range.toUpperCase()}
          </small>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={points}>
            <CartesianGrid stroke="#2a2b2b" vertical={false} />
            <XAxis dataKey="week" stroke="#646766" fontSize={10} />
            <YAxis stroke="#646766" fontSize={10} />
            <Tooltip
              contentStyle={{
                background: "#181a19",
                border: "1px solid #343635",
              }}
            />
            <Line
              type="monotone"
              dataKey="ctl"
              name="Krónikus terhelés"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="atl"
              name="Akut terhelés"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="tsb"
              name="Forma (TSB)"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </section>
      <div className="trend-bottom">
        <section className="card zone-card">
          <div className="section-head">
            <span className="eyebrow">ZÓNAIDŐ ELOSZLÁS · AKTUÁLIS HÉT</span>
            <small>{total} PERC</small>
          </div>
          {zoneValues.map((minutes, index) => (
            <div className="zone-row" key={index}>
              <MetricHelp term={`Z${index + 1}`}>
                <b>Z{index + 1}</b>
              </MetricHelp>
              <span>
                <i
                  style={{
                    width: `${total ? (minutes / total) * 100 : 0}%`,
                    background: colors[index],
                  }}
                />
              </span>
              <strong>{minutes}p</strong>
            </div>
          ))}
        </section>
        <section className="card dimensions">
          <div className="section-head">
            <span className="eyebrow">SZEMÉLYES FÓKUSZ</span>
            <small>{profile.goal.toUpperCase()}</small>
          </div>
          <div className="goal-progress">
            <strong>{profile.strengthRatio}%</strong>
            <span>ERŐ CÉL</span>
            <i>
              <b style={{ width: `${profile.strengthRatio}%` }} />
            </i>
          </div>
          <div className="goal-progress">
            <strong>{profile.weeklyHours}ó</strong>
            <span>HETI IDŐKERET</span>
            <i>
              <b
                style={{
                  width: `${Math.min(100, (profile.weeklyHours / 15) * 100)}%`,
                }}
              />
            </i>
          </div>
          {profile.eventName && (
            <div className="event-focus">
              <span className="eyebrow">KÖVETKEZŐ ESEMÉNY</span>
              <h2>{profile.eventName}</h2>
              <p>
                {eventDays !== null && eventDays >= 0
                  ? `${eventDays} nap van hátra.`
                  : "Az esemény dátuma elmúlt."}{" "}
                A trendeket a {profile.goal.toLowerCase()} célod szerint
                értelmezzük.
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function AdaptiveWeekPlanner({ profile, data, cloudState, onSave }) {
  const [open, setOpen] = useState(false),
    [saved, setSaved] = useState(false),
    result = buildAdaptiveWeek(profile, data, cloudState),
    dates = result.adapted.map((item) => item.date),
    save = () => {
      onSave({ plans: result.adapted, replacePlanDates: dates });
      setSaved(true);
      setOpen(false);
    };
  return (
    <section className="card adaptive-card">
      <div>
        <span className="eyebrow">ADAPTÍV KÖVETKEZŐ HÉT</span>
        <h2>
          {result.adjustment === 0
            ? "A terv tartható"
            : result.adjustment > 0
              ? "Kontrollált terhelésemelés"
              : "Regenerációhoz igazított könnyítés"}
        </h2>
        <p>{result.reasons[0]}</p>
        <div className="adaptive-signals">
          <span>
            Terhelhetőség <b>{result.readiness}/100</b>
          </span>
          <span>
            Tervkövetés{" "}
            <b>
              {result.adherence === null
                ? "nincs adat"
                : `${result.adherence}%`}
            </b>
          </span>
          <span>
            Elmaradt <b>{result.missed}</b>
          </span>
          <span>
            Volumen{" "}
            <b>
              {result.adjustment > 0 ? "+" : ""}
              {result.adjustment}%
            </b>
          </span>
        </div>
      </div>
      <button className="adaptive-open" onClick={() => setOpen(true)}>
        MÓDOSÍTÁSOK ÁTTEKINTÉSE
      </button>
      {saved && (
        <span className="adaptive-saved">
          A következő hét frissült a Naptárban.
        </span>
      )}
      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div
            className="modal adaptive-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <button className="close" onClick={() => setOpen(false)}>
              <X size={18} />
            </button>
            <span className="eyebrow">
              {new Date(`${result.start}T12:00:00`).toLocaleDateString(
                "hu-HU",
                { month: "long", day: "numeric" },
              )}{" "}
              –{" "}
              {new Date(`${result.end}T12:00:00`).toLocaleDateString("hu-HU", {
                month: "long",
                day: "numeric",
              })}
            </span>
            <h2>Mi változik a következő héten?</h2>
            <div className="adaptive-reasons">
              {result.reasons.map((reason) => (
                <p key={reason}>
                  <Sparkles size={15} />
                  <span>{reason}</span>
                </p>
              ))}
            </div>
            <div className="adaptive-comparison">
              {result.adapted.map((item, index) => {
                const before = result.base[index];
                return (
                  <div key={item.id}>
                    <time>
                      {new Date(`${item.date}T12:00:00`).toLocaleDateString(
                        "hu-HU",
                        { weekday: "short", month: "short", day: "numeric" },
                      )}
                    </time>
                    <span>
                      <b>{item.title}</b>
                      <small>
                        {before.duration}p · RPE {before.rpe} ·{" "}
                        {before.intensity}
                      </small>
                    </span>
                    <ChevronRight size={16} />
                    <span className="after">
                      <b>{item.duration} perc</b>
                      <small>
                        RPE {item.rpe} · {item.intensity}
                      </small>
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="adaptive-note">
              Az elmaradt edzéseket nem sűrítjük be. A javaslat sportdöntési
              támogatás, fájdalom vagy betegség esetén a saját közérzeted az
              elsődleges.
            </p>
            <div className="template-editor-actions">
              <button onClick={() => setOpen(false)}>Mégse</button>
              <button className="primary" onClick={save}>
                Adaptált hét mentése
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
function PeriodizationPlanner({ profile, data, plans, onSave }) {
  const [weeks, setWeeks] = useState(8),
    [open, setOpen] = useState(false),
    [replace, setReplace] = useState(true),
    [saved, setSaved] = useState(false),
    cycle = buildPeriodizedCycle(profile, data, weeks),
    generated = cycle.flatMap((week) => week.sessions),
    generatedDates = new Set(generated.map((item) => item.date)),
    conflicts = plans.filter((item) => generatedDates.has(item.date));
  const save = () => {
    onSave({ plans: generated, replacePlanDates: [...generatedDates] });
    setSaved(true);
    setOpen(false);
  };
  return (
    <section className="card periodization-card">
      <div>
        <span className="eyebrow">ESEMÉNYSPECIFIKUS PERIODIZÁCIÓ</span>
        <h2>
          {profile.eventName
            ? `${profile.eventName} felkészülési ciklus`
            : `${profile.goal} felkészülési ciklus`}
        </h2>
        <p>
          Fokozatos alapozás, építés, csúcsterhelés és könnyítés a saját heti
          időkeretedre osztva.
        </p>
      </div>
      <div className="periodization-actions">
        <div className="segmented">
          {[4, 8, 12].map((value) => (
            <button
              className={weeks === value ? "active" : ""}
              onClick={() => {
                setWeeks(value);
                setSaved(false);
              }}
              key={value}
            >
              {value} hét
            </button>
          ))}
        </div>
        <button className="primary" onClick={() => setOpen(true)}>
          TERV ELŐNÉZETE
        </button>
      </div>
      {saved && (
        <span className="periodization-saved">
          A ciklus edzései bekerültek a Naptárba.
        </span>
      )}
      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div
            className="modal periodization-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <button className="close" onClick={() => setOpen(false)}>
              <X size={18} />
            </button>
            <span className="eyebrow">{weeks} HETES FELKÉSZÜLÉSI CIKLUS</span>
            <h2>Heti fázisok és kulcsterhelés</h2>
            <p>
              A terv {generated.length} edzést oszt el a megadott edzésnapokra.
              Mentés után minden alkalom külön szerkeszthető a Naptárban.
            </p>
            <div className="periodization-weeks">
              {cycle.map((week) => (
                <details
                  open={week.index === 1 || week.index === cycle.length}
                  key={week.index}
                >
                  <summary>
                    <span>
                      <b>
                        {week.index}. hét · {week.phase}
                      </b>
                      <small>
                        {new Date(
                          `${week.weekStart}T12:00:00`,
                        ).toLocaleDateString("hu-HU", {
                          month: "short",
                          day: "numeric",
                        })}{" "}
                        · {week.sessions.length} edzés
                      </small>
                    </span>
                    <strong>
                      {week.volume}%<small> volumen</small>
                    </strong>
                  </summary>
                  <div className="periodization-week-detail">
                    <p>
                      <b>Heti fókusz:</b> {week.focus} ·{" "}
                      {Math.floor(week.minutes / 60)}ó {week.minutes % 60}p
                    </p>
                    {week.sessions.map((session) => (
                      <div key={session.id}>
                        <time>
                          {new Date(
                            `${session.date}T12:00:00`,
                          ).toLocaleDateString("hu-HU", {
                            weekday: "short",
                            month: "short",
                            day: "numeric",
                          })}
                        </time>
                        <span>{session.title}</span>
                        <small>
                          {session.duration}p · RPE {session.rpe}
                        </small>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
            {conflicts.length > 0 && (
              <label className="periodization-conflict">
                <input
                  type="checkbox"
                  checked={replace}
                  onChange={(event) => setReplace(event.target.checked)}
                />
                <span>
                  {conflicts.length} meglévő tervet lecserélek az érintett
                  napokon
                </span>
              </label>
            )}
            <div className="template-editor-actions">
              <button onClick={() => setOpen(false)}>Mégse</button>
              <button
                className="primary"
                disabled={conflicts.length > 0 && !replace}
                onClick={save}
              >
                Ciklus mentése a Naptárba
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
function GoalPage({ profile, onEdit, cloudState, onCloudPatch }) {
  const data = useDashboardData(),
    readiness = buildGoalReadiness(data, profile),
    status =
      readiness.score >= 80
        ? "jó úton"
        : readiness.score >= 60
          ? "épülő forma"
          : "figyelmet igényel";
  return (
    <>
      <PageHeader eyebrow="SZEMÉLYES CÉL" title="Felkészültség">
        <button className="goal-edit" onClick={onEdit}>
          CÉL SZERKESZTÉSE
        </button>
      </PageHeader>
      <main className="goal-layout">
        <section className="card goal-hero">
          <div className="goal-score">
            <strong>{readiness.score}</strong>
            <span>/ 100</span>
          </div>
          <div>
            <span className="eyebrow">{status.toUpperCase()}</span>
            <h2>{profile.eventName || profile.goal}</h2>
            <p>
              {profile.eventName && profile.eventDate
                ? `${readiness.eventDays >= 0 ? `${readiness.eventDays} nap van hátra` : `Az esemény dátuma ${Math.abs(readiness.eventDays)} napja elmúlt`}. `
                : ""}
              Az értékelés {readiness.recentCount} elmúlt 28 napos edzés, a heti
              keret és a jelenlegi regeneráció alapján készült.
            </p>
            <div className="goal-meta">
              <span>{profile.goal}</span>
              <span>{profile.weeklyHours} óra / hét</span>
              <span>{profile.strengthRatio}% erő</span>
              <span>Leghosszabb edzés: {readiness.longest}p</span>
            </div>
          </div>
        </section>
        <PeriodizationPlanner
          profile={profile}
          data={data}
          plans={cloudState?.plans || []}
          onSave={onCloudPatch}
        />
        <AdaptiveWeekPlanner
          profile={profile}
          data={data}
          cloudState={cloudState}
          onSave={onCloudPatch}
        />
        <section className="card goal-components">
          <div className="section-head">
            <span className="eyebrow">FELKÉSZÜLTSÉGI ÖSSZETEVŐK</span>
            <small>MAGYARÁZHATÓ MODELL</small>
          </div>
          {readiness.components.map((item) => (
            <div className="goal-component" key={item.name}>
              <div>
                <b>{item.name}</b>
                <strong>{item.score}</strong>
              </div>
              <span>
                <i style={{ width: `${item.score}%` }} />
              </span>
            </div>
          ))}
        </section>
        <aside className="card goal-gaps">
          <span className="eyebrow">KÖVETKEZŐ PRIORITÁSOK</span>
          <h2>
            {readiness.gaps[0] ===
            "nincs kiemelt hiány a jelenlegi adatok alapján"
              ? "Tartsd az irányt"
              : "Ezek zárják most a rést"}
          </h2>
          <ol>
            {readiness.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ol>
          <p>
            A pontszám sportteljesítményi döntéstámogatás, nem orvosi minősítés.
          </p>
        </aside>
      </main>
    </>
  );
}

function InsightsPage({ profile }) {
  const [accepted, setAccepted] = useState(false),
    data = useDashboardData(),
    view = personalizeDashboard(data, profile),
    week = view.week;
  let activityFeedback = [];
  try {
    activityFeedback = Object.values(
      JSON.parse(localStorage.getItem("hybrid-activity-feedback") || "{}"),
    );
  } catch {}
  const averageRpe = activityFeedback.length
      ? Math.round(
          (activityFeedback.reduce(
            (sum, item) => sum + Number(item.rpe || 0),
            0,
          ) /
            activityFeedback.length) *
            10,
        ) / 10
      : null,
    feedbackFinding = averageRpe
      ? [
          "Saját terhelésérzet",
          `${activityFeedback.length} értékelt edzés átlagos RPE-je ${averageRpe}/10. ${averageRpe >= 8 ? "A következő terhelhető nap előtt ellenőrizd a regenerációt." : "A szubjektív terhelés kontrollált tartományban van."}`,
          Math.min(90, 55 + activityFeedback.length * 5),
          averageRpe >= 8 ? "amber" : "strong",
        ]
      : null;
  const findings = [
    ...view.insights.map((text, index) => [
      index === 0 ? "Heti keret" : index === 1 ? "Edzésarány" : "Célfókusz",
      text,
      Math.max(55, 90 - index * 12),
      index === 1 ? "amber" : "strong",
    ]),
    ...(feedbackFinding ? [feedbackFinding] : []),
  ];
  const nextWeek =
    week.progress > 110 || Number(data?.week?.change_pct || 0) > 20
      ? "A következő hét legyen stabilizáló hét"
      : `A következő hét fókusza: ${profile.goal.toLowerCase()}`;
  return (
    <>
      <PageHeader eyebrow="INSIGHTS" title="Mi működik nálam" />
      <div className="insights-layout">
        <div>
          <section className="card findings">
            <div className="section-head">
              <span className="eyebrow">SZEMÉLYES FELISMERÉSEK</span>
              <small>GARMIN + PROFIL + RPE · {findings.length} JELZÉS</small>
            </div>
            {findings.map(([t, d, v, tone]) => (
              <button key={t}>
                <span className={`finding-icon ${tone}`}>
                  <TrendingUp size={15} />
                </span>
                <div>
                  <b>{t}</b>
                  <p>{d}</p>
                </div>
                <span className="finding-score">
                  <i style={{ width: `${v}%` }} />
                  <small>{v}% BIZONYOSSÁG</small>
                </span>
              </button>
            ))}
          </section>
          <section className="weekly-recap card">
            <div className="section-head">
              <span className="eyebrow">AKTUÁLIS HETI VISSZATEKINTÉS</span>
            </div>
            <div>
              {[
                [week.totalLoad.toLocaleString("hu-HU"), "ÖSSZTERHELÉS"],
                [
                  `${Math.floor(week.actualMinutes / 60)}ó ${week.actualMinutes % 60}p`,
                  "EDZÉSIDŐ",
                ],
                [`${week.progress}%`, "IDŐKERET"],
                [String(data?.readiness ?? "—"), "TERHELHETŐSÉG"],
              ].map(([v, l]) => (
                <span key={l}>
                  <strong>{v}</strong>
                  <small>{l}</small>
                </span>
              ))}
            </div>
          </section>
        </div>
        <aside>
          <section className="card coach-card">
            <span className="eyebrow">HETI AJÁNLÁS</span>
            <h2>{nextWeek}</h2>
            <p>
              {data?.week?.recommendations?.[0] ||
                `A heti struktúrát a ${profile.weeklyHours} órás keretedhez és a ${profile.strengthRatio}%-os erőcélodhoz igazítjuk.`}
            </p>
            <div className="coach-actions">
              <button onClick={() => setAccepted(true)}>
                {accepted ? "ELFOGADVA" : "ELFOGADOM"}
              </button>
              <button>MAJD KÉSŐBB</button>
            </div>
          </section>
          <section className="card locked">
            <LockKeyhole size={16} />
            <div>
              <b>Következő mélyelemzés</b>
              <p>
                A felismerések a következő Garmin-szinkron és edzés-visszajelzés
                után újraszámolódnak.
              </p>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}

function JournalPage() {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("Mind");
  const visible = sessions.filter(
    (x) =>
      (type === "Mind" || x[1] === type) &&
      x.slice(0, 3).join(" ").toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeader eyebrow="NAPLÓ" title="Edzések">
        <div className="journal-search">
          <Search size={14} />
          <input
            aria-label="Keresés"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Keresés az edzésekben"
          />
        </div>
      </PageHeader>
      <div className="journal-filters">
        <Filter size={14} />
        {["Mind", "Futás", "Erő", "Mobilitás", "Túrázás"].map((x) => (
          <button
            key={x}
            className={type === x ? "active" : ""}
            onClick={() => setType(x)}
          >
            {x}
          </button>
        ))}
      </div>
      <section className="card table-wrap">
        <table>
          <thead>
            <tr>
              {[
                "DÁTUM",
                "TÍPUS",
                "EDZÉS",
                "IDŐ",
                "ÁTL. PULZUS",
                "RPE",
                "TERHELÉS",
                "TERV",
              ].map((x) => (
                <th key={x}>{x}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>
                    {j === 1 ? (
                      <span className={`sport ${cell}`}>
                        {cell === "Erő" ? (
                          <Dumbbell size={13} />
                        ) : (
                          <Activity size={13} />
                        )}{" "}
                        {cell}
                      </span>
                    ) : j === 7 ? (
                      <span
                        className={`status ${cell.includes("TERV") ? "good" : "neutral"}`}
                      >
                        {cell}
                      </span>
                    ) : (
                      cell
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && (
          <div className="empty">Nincs a szűrésnek megfelelő edzés.</div>
        )}
      </section>
    </>
  );
}

function ActivityDetail({ activity, feedback, onSave, onClose }) {
  const [draft, setDraft] = useState(
      () => feedback || { rpe: 5, feeling: "rendben", note: "" },
    ),
    set = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal activity-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close" onClick={onClose}>
          <X size={18} />
        </button>
        <span className="eyebrow">GARMIN EDZÉSRÉSZLET</span>
        <h2>{activity.name}</h2>
        <p>
          {new Date(activity.date).toLocaleDateString("hu-HU", {
            year: "numeric",
            month: "long",
            day: "numeric",
            weekday: "long",
          })}
        </p>
        <div className="activity-stats">
          {[
            [activity.type, "TÍPUS"],
            [`${activity.durationMin}p`, "IDŐ"],
            [activity.avgHr ? `${activity.avgHr} bpm` : "—", "ÁTL. PULZUS"],
            [activity.distanceKm ? `${activity.distanceKm} km` : "—", "TÁV"],
            [activity.load, "TERHELÉS"],
          ].map(([value, label]) => (
            <span key={label}>
              <strong>{value}</strong>
              <small>{label}</small>
            </span>
          ))}
        </div>
        <div className="feedback-form">
          <span className="eyebrow">SAJÁT VISSZAJELZÉS</span>
          <div className="field">
            <label>Érzékelt terhelés · RPE</label>
            <div className="rpe-picker">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
                <button
                  key={value}
                  className={draft.rpe === value ? "selected" : ""}
                  onClick={() => set("rpe", value)}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Edzés utáni közérzet</label>
            <div className="feeling-picker">
              {[
                ["kiváló", "Kiváló"],
                ["rendben", "Rendben"],
                ["nehéz", "Nehéz"],
                ["rossz", "Rossz"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  className={draft.feeling === value ? "selected" : ""}
                  onClick={() => set("feeling", value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Megjegyzés</label>
            <textarea
              value={draft.note}
              onChange={(event) => set("note", event.target.value)}
              placeholder="Mi ment jól, min változtatnál?"
            />
          </div>
        </div>
        <div className="activity-actions">
          <button onClick={onClose}>Mégse</button>
          <button
            className="primary"
            onClick={() =>
              onSave({ ...draft, savedAt: new Date().toISOString() })
            }
          >
            Visszajelzés mentése
          </button>
        </div>
      </div>
    </div>
  );
}
function LiveJournalPage({ cloudState, onCloudPatch }) {
  const data = useDashboardData(),
    [query, setQuery] = useState(""),
    [type, setType] = useState("Mind"),
    [selected, setSelected] = useState(null),
    [feedback, setFeedback] = useState(() => {
      try {
        return JSON.parse(
          localStorage.getItem("hybrid-activity-feedback") || "{}",
        );
      } catch {
        return {};
      }
    });
  useEffect(() => {
    if (cloudState?.feedback) {
      setFeedback(cloudState.feedback);
      localStorage.setItem(
        "hybrid-activity-feedback",
        JSON.stringify(cloudState.feedback),
      );
    }
  }, [cloudState]);
  const rows = data?.sessions || [];
  const types = ["Mind", ...new Set(rows.map((x) => x.type))],
    visible = rows.filter(
      (x) =>
        (type === "Mind" || x.type === type) &&
        `${x.name} ${x.type} ${x.date}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    ),
    save = (id, value) => {
      const next = { ...feedback, [id]: value };
      setFeedback(next);
      localStorage.setItem("hybrid-activity-feedback", JSON.stringify(next));
      onCloudPatch({ feedback: { activityId: id, value } });
      setSelected(null);
    };
  return (
    <>
      <PageHeader eyebrow="NAPLÓ" title="Edzések">
        <div className="journal-search">
          <Search size={14} />
          <input
            aria-label="Keresés"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Keresés az edzésekben"
          />
        </div>
      </PageHeader>
      <div className="journal-filters">
        <Filter size={14} />
        {types.map((x) => (
          <button
            key={x}
            className={type === x ? "active" : ""}
            onClick={() => setType(x)}
          >
            {x}
          </button>
        ))}
      </div>
      <section className="card table-wrap">
        <table>
          <thead>
            <tr>
              {[
                "DÁTUM",
                "TÍPUS",
                "EDZÉS",
                "IDŐ",
                "ÁTL. PULZUS",
                "TÁV",
                "TERHELÉS",
                "RPE",
                "VISSZAJELZÉS",
              ].map((x) => (
                <th key={x}>{x}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr
                className="activity-row"
                role="button"
                tabIndex="0"
                key={row.id}
                onClick={() => setSelected(row)}
                onKeyDown={(event) => event.key === "Enter" && setSelected(row)}
              >
                <td>{new Date(row.date).toLocaleDateString("hu-HU")}</td>
                <td>
                  <span className={`sport ${row.type}`}>
                    {row.type === "Erő" ? (
                      <Dumbbell size={13} />
                    ) : (
                      <Activity size={13} />
                    )}{" "}
                    {row.type}
                  </span>
                </td>
                <td>{row.name}</td>
                <td>{row.durationMin}p</td>
                <td>{row.avgHr ? `${row.avgHr} bpm` : "—"}</td>
                <td>{row.distanceKm ? `${row.distanceKm} km` : "—"}</td>
                <td>{row.load}</td>
                <td>{feedback[row.id]?.rpe || "—"}</td>
                <td>
                  <span
                    className={`status ${feedback[row.id] ? "good" : "neutral"}`}
                  >
                    {feedback[row.id] ? "RÖGZÍTVE" : "MEGNYITÁS"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && (
          <div className="empty">Nincs a szűrésnek megfelelő edzés.</div>
        )}
      </section>
      {selected && (
        <ActivityDetail
          activity={selected}
          feedback={feedback[selected.id]}
          onSave={(value) => save(selected.id, value)}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}

const accentOptions = [
  {
    id: "teal",
    name: "Teal",
    color: "#14b8a6",
    soft: "rgba(20,184,166,.16)",
    deep: "#123b36",
    text: "#5eead4",
  },
  {
    id: "blue",
    name: "Kék",
    color: "#3b82f6",
    soft: "rgba(59,130,246,.16)",
    deep: "#17335f",
    text: "#93c5fd",
  },
  {
    id: "violet",
    name: "Ibolya",
    color: "#8b5cf6",
    soft: "rgba(139,92,246,.16)",
    deep: "#35245f",
    text: "#c4b5fd",
  },
  {
    id: "orange",
    name: "Narancs",
    color: "#f59e0b",
    soft: "rgba(245,158,11,.16)",
    deep: "#5b3b0d",
    text: "#fcd34d",
  },
  {
    id: "rose",
    name: "Rózsa",
    color: "#f43f5e",
    soft: "rgba(244,63,94,.16)",
    deep: "#5c1d2a",
    text: "#fda4af",
  },
];
function AccentPicker({ value, onChange }) {
  return (
    <div className="accent-grid" role="radiogroup" aria-label="Akcentusszín">
      {accentOptions.map((option) => (
        <button
          type="button"
          role="radio"
          aria-checked={value === option.id}
          className={`accent-option ${value === option.id ? "selected" : ""}`}
          style={{ "--choice": option.color }}
          key={option.id}
          onClick={() => onChange(option.id)}
        >
          <i />
          <b>{option.name}</b>
        </button>
      ))}
    </div>
  );
}
const resizeProfileImage = (file) =>
  new Promise((resolve, reject) => {
    if (!file?.type?.startsWith("image/")) {
      reject(new Error("Csak képfájl tölthető fel."));
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      reject(new Error("A kiválasztott kép legfeljebb 8 MB lehet."));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("A kép nem olvasható."));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () =>
        reject(new Error("A kép formátuma nem támogatott."));
      image.onload = () => {
        const side = Math.min(image.width, image.height),
          canvas = document.createElement("canvas");
        canvas.width = 256;
        canvas.height = 256;
        canvas
          .getContext("2d")
          .drawImage(
            image,
            (image.width - side) / 2,
            (image.height - side) / 2,
            side,
            side,
            0,
            0,
            256,
            256,
          );
        const value = canvas.toDataURL("image/webp", 0.78);
        value.length > 220000
          ? reject(
              new Error(
                "A tömörített kép túl nagy. Válassz egyszerűbb vagy kisebb képet.",
              ),
            )
          : resolve(value);
      };
      image.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
function AvatarPicker({ profile, onChange }) {
  const [error, setError] = useState(""),
    choose = (value) => {
      setError("");
      onChange({ ...profile, avatarPreset: value, avatarImage: "" });
    },
    upload = async (event) => {
      try {
        const avatarImage = await resizeProfileImage(event.target.files?.[0]);
        setError("");
        onChange({ ...profile, avatarPreset: "photo", avatarImage });
      } catch (reason) {
        setError(reason.message);
      }
      event.target.value = "";
    };
  return (
    <div className="avatar-settings">
      <div className="avatar-preview">
        <AvatarView profile={profile} size="large" />
        <div>
          <b>{profile.name}</b>
          <span>
            {profile.avatarImage ? "Saját profilkép" : "Választott avatar"}
          </span>
        </div>
      </div>
      <div
        className="avatar-options"
        role="radiogroup"
        aria-label="Avatar választása"
      >
        {Object.entries(avatarPresets).map(([id, Icon]) => (
          <button
            type="button"
            role="radio"
            aria-checked={!profile.avatarImage && profile.avatarPreset === id}
            className={
              !profile.avatarImage && profile.avatarPreset === id
                ? "selected"
                : ""
            }
            onClick={() => choose(id)}
            key={id}
          >
            <Icon aria-hidden="true" />
            <span>
              {
                {
                  athlete: "Sportoló",
                  strength: "Erő",
                  endurance: "Állóképesség",
                  classic: "Klasszikus",
                }[id]
              }
            </span>
          </button>
        ))}
      </div>
      <label className="avatar-upload">
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={upload}
        />
        <span>Profilkép feltöltése</span>
        <small>JPG, PNG vagy WebP · legfeljebb 8 MB</small>
      </label>
      {error && (
        <p className="avatar-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
function GarminConnectionCard({ onStatus }) {
  const [status, setStatus] = useState(null),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/garmin")
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error);
        setStatus(body);
        onStatus?.(body);
      })
      .catch((reason) =>
        setError(reason.message || "A kapcsolat állapota nem tölthető be."),
      );
  }, []);
  const connect = async (event) => {
      event.preventDefault();
      setBusy(true);
      setError("");
      try {
        const response = await fetch("/api/garmin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
          }),
          body = await response.json();
        if (!response.ok) throw new Error(body.error);
        setStatus(body);
        onStatus?.(body);
        setPassword("");
      } catch (reason) {
        setError(reason.message);
      } finally {
        setBusy(false);
      }
    },
    disconnect = async () => {
      setBusy(true);
      setError("");
      try {
        const response = await fetch("/api/garmin", { method: "DELETE" }),
          body = await response.json();
        if (!response.ok) throw new Error(body.error);
        setStatus(body);
        onStatus?.(body);
        setEmail("");
        setPassword("");
      } catch (reason) {
        setError(reason.message);
      } finally {
        setBusy(false);
      }
    };
  return (
    <section className="card garmin-connection">
      <span className="eyebrow">ADATFORRÁS</span>
      <div className="connection-heading">
        <div>
          <h2>Garmin Connect</h2>
          <p>A saját Garmin-előzményeid csak a te fiókodhoz kerülnek.</p>
        </div>
        <span
          className={
            status?.status === "connected" ? "connected" : "disconnected"
          }
        >
          {status?.status === "connected"
            ? "CSATLAKOZTATVA"
            : "NINCS KAPCSOLAT"}
        </span>
      </div>
      {status?.status === "connected" ? (
        <>
          <div className="connected-account">
            <Activity size={22} />
            <div>
              <b>{status.email_hint}</b>
              <small>A hitelesítő adatok titkosítva vannak tárolva.</small>
            </div>
          </div>
          <div className="connection-actions">
            <button
              className="danger-outline"
              disabled={busy}
              onClick={disconnect}
            >
              Garmin leválasztása
            </button>
          </div>
        </>
      ) : (
        <form onSubmit={connect}>
          <label>
            Garmin e-mail-cím
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Garmin-jelszó
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <p className="connection-note">
            <LockKeyhole size={15} /> A jelszót a szerver titkosítja, és soha
            nem küldi vissza a böngészőnek. Az MFA-val védett fiókokhoz külön
            hitelesítési lépést építünk.
          </p>
          <button className="primary" disabled={busy}>
            {busy ? "Mentés…" : "Garmin csatlakoztatása"}
          </button>
        </form>
      )}
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
function SettingsPage({
  accent,
  onAccent,
  profile,
  onProfileSave,
  user,
  onLogout,
  onGarminStatus,
}) {
  const [draft, setDraft] = useState(accent),
    [avatarDraft, setAvatarDraft] = useState(profile),
    [saved, setSaved] = useState(false);
  useEffect(() => setAvatarDraft(profile), [profile]);
  return (
    <>
      <PageHeader eyebrow="SZEMÉLYRE SZABÁS" title="Beállítások" />
      <main className="accent-page settings-stack">
        <GarminConnectionCard onStatus={onGarminStatus} />
        <section className="card accent-card">
          <span className="eyebrow">PROFILKÉP</span>
          <h2>Személyes megjelenés</h2>
          <p>
            Tölts fel saját profilképet, vagy válassz a sportos avatarok közül.
          </p>
          <AvatarPicker
            profile={avatarDraft}
            onChange={(value) => {
              setAvatarDraft(value);
              setSaved(false);
            }}
          />
          <div className="accent-actions">
            <button onClick={() => setAvatarDraft(profile)}>
              Visszaállítás
            </button>
            <button
              className="primary"
              onClick={() => {
                onProfileSave(avatarDraft);
                setSaved(true);
              }}
            >
              {saved ? "Mentve" : "Profilkép mentése"}
            </button>
          </div>
        </section>
        <section className="card accent-card">
          <span className="eyebrow">MEGJELENÉS</span>
          <h2>Akcentusszín</h2>
          <p>
            Válaszd ki azt a színt, amely a kiemeléseken, grafikonokon, aktív
            menüpontokon és elsődleges műveleteken jelenjen meg.
          </p>
          <AccentPicker
            value={draft}
            onChange={(value) => {
              setDraft(value);
              setSaved(false);
            }}
          />
          <div className="accent-actions">
            <button onClick={() => setDraft(accent)}>Visszaállítás</button>
            <button
              className="primary"
              onClick={() => {
                onAccent(draft);
                setSaved(true);
              }}
            >
              {saved ? "Mentve" : "Választás mentése"}
            </button>
          </div>
        </section>
        <section className="card account-card">
          <span className="eyebrow">FIÓK</span>
          <h2>{user?.name}</h2>
          <p>{user?.email}</p>
          <button className="logout-button" onClick={onLogout}>
            <LogOut size={17} /> Kijelentkezés
          </button>
        </section>
      </main>
    </>
  );
}
function Onboarding({ accent, onAccent, onDone }) {
  const [draft, setDraft] = useState(accent);
  return (
    <div className="onboarding-backdrop">
      <section className="onboarding">
        <span className="eyebrow">ÜDV A HYBRID ATHLETE-BEN</span>
        <h1>Tedd személyessé a felületet</h1>
        <p>
          Válassz egy akcentusszínt. A teal az alapértelmezett, és a
          választásodat később bármikor módosíthatod a Beállításokban.
        </p>
        <AccentPicker value={draft} onChange={setDraft} />
        <div className="accent-actions">
          <button
            className="primary"
            onClick={() => {
              onAccent(draft);
              onDone();
            }}
          >
            Folytatás
          </button>
        </div>
      </section>
    </div>
  );
}

const defaultProfile = {
  name: "Attila",
  experience: "középhaladó",
  goal: "Hibrid teljesítmény",
  eventName: "",
  eventDate: "",
  weeklyHours: 8,
  strengthRatio: 30,
  trainingDays: ["H", "K", "Sze", "Cs", "P", "Szo"],
  restDay: "V",
  limitations: "",
  preference: "kiegyensúlyozott",
  avatarPreset: "athlete",
  avatarImage: "",
};
function readProfile() {
  try {
    return {
      ...defaultProfile,
      ...JSON.parse(localStorage.getItem("hybrid-profile") || "{}"),
    };
  } catch {
    return defaultProfile;
  }
}
const days = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];
function DayPicker({ value, onChange }) {
  return (
    <div className="day-picker">
      {days.map((day) => (
        <button
          type="button"
          key={day}
          className={value.includes(day) ? "selected" : ""}
          onClick={() =>
            onChange(
              value.includes(day)
                ? value.filter((x) => x !== day)
                : [...value, day],
            )
          }
        >
          {day}
        </button>
      ))}
    </div>
  );
}
function ProfileFields({ value, onChange }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  return (
    <div className="form-grid">
      <div className="field">
        <label>Név</label>
        <input
          value={value.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Hogyan szólíthatunk?"
        />
      </div>
      <div className="field">
        <label>Tapasztalati szint</label>
        <select
          value={value.experience}
          onChange={(e) => set("experience", e.target.value)}
        >
          <option>kezdő</option>
          <option>középhaladó</option>
          <option>haladó</option>
        </select>
      </div>
      <div className="field">
        <label>Elsődleges cél</label>
        <select
          value={value.goal}
          onChange={(e) => set("goal", e.target.value)}
        >
          <option>Hibrid teljesítmény</option>
          <option>Futóteljesítmény</option>
          <option>Erőfejlesztés</option>
          <option>Hegyi állóképesség</option>
          <option>Általános egészség</option>
        </select>
      </div>
      <div className="field">
        <label>Edzésirány</label>
        <select
          value={value.preference}
          onChange={(e) => set("preference", e.target.value)}
        >
          <option value="kiegyensúlyozott">Kiegyensúlyozott</option>
          <option value="teljesítmény">Teljesítményközpontú</option>
          <option value="regeneráció">Regenerációközpontú</option>
        </select>
      </div>
      <div className="field">
        <label>Következő esemény</label>
        <input
          value={value.eventName}
          onChange={(e) => set("eventName", e.target.value)}
          placeholder="Például: félmaraton"
        />
      </div>
      <div className="field">
        <label>Esemény dátuma</label>
        <input
          type="date"
          value={value.eventDate}
          onChange={(e) => set("eventDate", e.target.value)}
        />
      </div>
      <div className="field">
        <label>Heti edzésidő</label>
        <input
          type="number"
          min="1"
          max="30"
          value={value.weeklyHours}
          onChange={(e) => set("weeklyHours", Number(e.target.value))}
        />
        <small>Óra hetente</small>
      </div>
      <div className="field">
        <label>Erőedzés aránya</label>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={value.strengthRatio}
          onChange={(e) => set("strengthRatio", Number(e.target.value))}
        />
        <small>
          {value.strengthRatio}% erő · {100 - value.strengthRatio}% kardió
        </small>
      </div>
      <div className="field wide">
        <label>Elérhető edzésnapok</label>
        <DayPicker
          value={value.trainingDays}
          onChange={(next) => set("trainingDays", next)}
        />
      </div>
      <div className="field">
        <label>Preferált pihenőnap</label>
        <select
          value={value.restDay}
          onChange={(e) => set("restDay", e.target.value)}
        >
          {days.map((day) => (
            <option key={day}>{day}</option>
          ))}
        </select>
      </div>
      <div className="field wide">
        <label>Korlátozás vagy érzékenység (opcionális)</label>
        <textarea
          value={value.limitations}
          onChange={(e) => set("limitations", e.target.value)}
          placeholder="Például korábbi sérülés, kerülendő mozgás vagy terhelési korlát"
        />
      </div>
    </div>
  );
}
function ProfilePage({ profile, onSave }) {
  const [draft, setDraft] = useState(profile),
    [saved, setSaved] = useState(false);
  useEffect(() => setDraft(profile), [profile]);
  return (
    <>
      <PageHeader eyebrow="SZEMÉLYES ALAPOK" title="Profil" />
      <main className="profile-page">
        <section className="card profile-card">
          <span className="eyebrow">EDZÉSPROFIL</span>
          <h2>Az ajánlások személyes kerete</h2>
          <ProfileFields
            value={draft}
            onChange={(value) => {
              setDraft(value);
              setSaved(false);
            }}
          />
          <div className="profile-save">
            {saved && <span>Változtatások elmentve</span>}
            <button
              className="primary"
              onClick={() => {
                onSave(draft);
                setSaved(true);
              }}
            >
              Profil mentése
            </button>
          </div>
        </section>
        <aside className="card profile-summary">
          <span className="eyebrow">ÖSSZEFOGLALÓ</span>
          <h2>Jelenlegi profil</h2>
          <div className="summary-name">
            <AvatarView profile={profile} size="large" />
            <div>
              <strong>{profile.name}</strong>
              <small>{profile.experience}</small>
            </div>
          </div>
          <div className="summary-list">
            <div>
              <span>Fő cél</span>
              <b>{profile.goal}</b>
            </div>
            <div>
              <span>Heti keret</span>
              <b>{profile.weeklyHours} óra</b>
            </div>
            <div>
              <span>Erő / kardió</span>
              <b>
                {profile.strengthRatio}% / {100 - profile.strengthRatio}%
              </b>
            </div>
            <div>
              <span>Edzésnapok</span>
              <b>{profile.trainingDays.join(", ")}</b>
            </div>
            <div>
              <span>Pihenőnap</span>
              <b>{profile.restDay}</b>
            </div>
            <div>
              <span>Következő esemény</span>
              <b>{profile.eventName || "Nincs megadva"}</b>
            </div>
          </div>
        </aside>
      </main>
    </>
  );
}
function PersonalOnboarding({ profile, accent, onAccent, onSave, onDone }) {
  const [step, setStep] = useState(0),
    [draft, setDraft] = useState(profile),
    [color, setColor] = useState(accent);
  const set = (key, value) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const nextAllowed = step !== 0 || draft.name.trim().length > 0;
  return (
    <div className="onboarding-backdrop">
      <section className="wizard">
        <div className="wizard-progress">
          {[0, 1, 2, 3].map((index) => (
            <i key={index} className={index <= step ? "active" : ""} />
          ))}
        </div>
        {step === 0 && (
          <>
            <span className="eyebrow">1 / 4 · ALAPOK</span>
            <h1>Ismerjük meg az edzésmúltad</h1>
            <p className="wizard-intro">
              Ezek az adatok segítenek a terhelés és az ajánlások megfelelő
              értelmezésében.
            </p>
            <div className="form-grid">
              <div className="field">
                <label>Név</label>
                <input
                  autoFocus
                  value={draft.name}
                  onChange={(e) => set("name", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Tapasztalati szint</label>
                <select
                  value={draft.experience}
                  onChange={(e) => set("experience", e.target.value)}
                >
                  <option>kezdő</option>
                  <option>középhaladó</option>
                  <option>haladó</option>
                </select>
              </div>
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <span className="eyebrow">2 / 4 · CÉL</span>
            <h1>Mi felé szeretnél haladni?</h1>
            <p className="wizard-intro">
              A cél módosítja a kardió, erő és regeneráció súlyát az
              ajánlásokban.
            </p>
            <div className="choice-grid">
              {[
                "Hibrid teljesítmény",
                "Futóteljesítmény",
                "Erőfejlesztés",
                "Hegyi állóképesség",
                "Általános egészség",
              ].map((goal) => (
                <button
                  key={goal}
                  className={draft.goal === goal ? "selected" : ""}
                  onClick={() => set("goal", goal)}
                >
                  {goal}
                </button>
              ))}
            </div>
            <div className="form-grid" style={{ marginTop: 18 }}>
              <div className="field">
                <label>Következő esemény (opcionális)</label>
                <input
                  value={draft.eventName}
                  onChange={(e) => set("eventName", e.target.value)}
                  placeholder="Például: félmaraton"
                />
              </div>
              <div className="field">
                <label>Dátuma</label>
                <input
                  type="date"
                  value={draft.eventDate}
                  onChange={(e) => set("eventDate", e.target.value)}
                />
              </div>
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <span className="eyebrow">3 / 4 · HETI KERET</span>
            <h1>Illesszük az edzést az életedhez</h1>
            <p className="wizard-intro">
              Az ajánlások csak a valóban rendelkezésedre álló napokkal és
              idővel számolnak.
            </p>
            <div className="form-grid">
              <div className="field">
                <label>Heti edzésidő</label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={draft.weeklyHours}
                  onChange={(e) => set("weeklyHours", Number(e.target.value))}
                />
                <small>Óra hetente</small>
              </div>
              <div className="field">
                <label>Erőedzés aránya</label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={draft.strengthRatio}
                  onChange={(e) => set("strengthRatio", Number(e.target.value))}
                />
                <small>
                  {draft.strengthRatio}% erő · {100 - draft.strengthRatio}%
                  kardió
                </small>
              </div>
              <div className="field wide">
                <label>Elérhető edzésnapok</label>
                <DayPicker
                  value={draft.trainingDays}
                  onChange={(value) => set("trainingDays", value)}
                />
              </div>
              <div className="field">
                <label>Preferált pihenőnap</label>
                <select
                  value={draft.restDay}
                  onChange={(e) => set("restDay", e.target.value)}
                >
                  {days.map((day) => (
                    <option key={day}>{day}</option>
                  ))}
                </select>
              </div>
              <div className="field wide">
                <label>Korlátozás (opcionális)</label>
                <textarea
                  value={draft.limitations}
                  onChange={(e) => set("limitations", e.target.value)}
                  placeholder="Korábbi sérülés, érzékenység vagy kerülendő terhelés"
                />
              </div>
            </div>
          </>
        )}
        {step === 3 && (
          <>
            <span className="eyebrow">4 / 4 · MEGJELENÉS</span>
            <h1>Válaszd ki az akcentusszíned</h1>
            <p className="wizard-intro">
              A választás később bármikor módosítható a Beállításokban.
            </p>
            <AccentPicker value={color} onChange={setColor} />
          </>
        )}
        <div className="wizard-actions">
          <button
            disabled={step === 0}
            onClick={() => setStep((value) => Math.max(0, value - 1))}
          >
            Vissza
          </button>
          <div className="right">
            {step < 3 ? (
              <button
                className="primary"
                disabled={!nextAllowed}
                onClick={() => setStep((value) => value + 1)}
              >
                Folytatás
              </button>
            ) : (
              <button
                className="primary"
                onClick={() => {
                  onAccent(color);
                  onSave(draft);
                  onDone();
                }}
              >
                Profil létrehozása
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function Placeholder({ page }) {
  return (
    <>
      <PageHeader eyebrow="HYBRID ATHLETE" title={page} />
      <div className="placeholder card">
        <BarChart3 size={26} />
        <h2>{page}</h2>
        <p>
          Ez a nézet a következő migrációs lépésben kapja meg a végleges
          felületét.
        </p>
      </div>
    </>
  );
}

async function authRequest(payload) {
  const response = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
    body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "A fiókművelet sikertelen.");
  return body.user;
}
function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login"),
    [name, setName] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    submit = async (event) => {
      event.preventDefault();
      setBusy(true);
      setError("");
      try {
        onAuthenticated(
          await authRequest({ action: mode, email, password, name }),
        );
      } catch (reason) {
        setError(reason.message);
      } finally {
        setBusy(false);
      }
    };
  return (
    <main className="auth-shell">
      <section className="auth-brand">
        <img src={brandMarkUrl} alt="Hybrid Athlete" />
        <span className="eyebrow">HYBRID ATHLETE</span>
        <h1>
          A teljesítményed.
          <br />
          Érthetően.
        </h1>
        <p>
          Személyes edzésadatok, fejlődéstörténet és döntéstámogatás egy
          biztonságos fiókban.
        </p>
      </section>
      <section className="auth-card card">
        <div className="auth-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Bejelentkezés
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Regisztráció
          </button>
        </div>
        <span className="eyebrow">
          {mode === "login" ? "ÜDV ÚJRA" : "ÚJ SPORTOLÓI FIÓK"}
        </span>
        <h2>
          {mode === "login"
            ? "Lépj be a dashboardodba"
            : "Hozd létre a saját tered"}
        </h2>
        <form onSubmit={submit}>
          {mode === "register" && (
            <label>
              Név
              <input
                autoComplete="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength="80"
              />
            </label>
          )}
          <label>
            E-mail-cím
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Jelszó
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength="10"
              required
            />
            <small>Legalább 10 karakter</small>
          </label>
          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy
              ? "Feldolgozás…"
              : mode === "login"
                ? "Bejelentkezés"
                : "Fiók létrehozása"}
          </button>
        </form>
        <p className="auth-privacy">
          <LockKeyhole size={15} /> A munkamenetet biztonságos, HttpOnly cookie
          védi. A Garmin-adataid elkülönítve maradnak.
        </p>
      </section>
    </main>
  );
}

const emptyPlan = (date) => ({
  id: "",
  date,
  type: "Kardió",
  title: "Zone 2 alapozás",
  duration: 60,
  intensity: "közepes",
  rpe: 5,
  purpose: "",
  note: "",
  status: "planned",
});
const activityMatchesType = (plan, activity) =>
  plan.type === "Kardió"
    ? ["Futás", "Túrázás", "Kerékpár", "Kardió"].includes(activity.type)
    : plan.type === activity.type;
function evaluatePlan(plan, activities, today) {
  const manual =
      plan.matchedActivityId &&
      activities.find(
        (item) => String(item.id) === String(plan.matchedActivityId),
      ),
    automatic = activities.find(
      (item) => item.date === plan.date && activityMatchesType(plan, item),
    ),
    activity = manual || automatic,
    method = manual ? "kézi" : automatic ? "automatikus" : null;
  if (!activity)
    return {
      activity: null,
      method,
      status: plan.date < today ? "elmaradt" : "tervezett",
      difference: null,
    };
  const difference = Math.round(
      Number(activity.durationMin || 0) - Number(plan.duration || 0),
    ),
    ratio =
      Number(activity.durationMin || 0) /
      Math.max(1, Number(plan.duration || 0));
  return {
    activity,
    method,
    status:
      ratio < 0.8
        ? "részben teljesült"
        : ratio <= 1.2
          ? "teljesült"
          : "túlteljesült",
    difference,
  };
}
function PlanEditor({ value, activities, onSave, onDelete, onClose }) {
  const [draft, setDraft] = useState(value),
    set = (key, next) => setDraft((current) => ({ ...current, [key]: next })),
    valid = draft.title.trim() && draft.date;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal plan-editor"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close" onClick={onClose}>
          <X size={18} />
        </button>
        <span className="eyebrow">
          {draft.id ? "EDZÉSTERV SZERKESZTÉSE" : "ÚJ EDZÉS TERVEZÉSE"}
        </span>
        <h2>{draft.id ? draft.title : "Új edzés"}</h2>
        <div className="plan-form">
          <div className="field">
            <label>Tervezett nap</label>
            <input
              type="date"
              value={draft.date}
              onChange={(event) => set("date", event.target.value)}
            />
          </div>
          <div className="field">
            <label>Típus</label>
            <select
              value={draft.type}
              onChange={(event) => set("type", event.target.value)}
            >
              {[
                "Kardió",
                "Erő",
                "Futás",
                "Túrázás",
                "Kerékpár",
                "Mobilitás",
                "Pihenő",
              ].map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </div>
          <div className="field wide">
            <label>Edzés neve</label>
            <input
              value={draft.title}
              maxLength="160"
              onChange={(event) => set("title", event.target.value)}
              placeholder="Például: Zone 2 futás"
            />
          </div>
          <div className="field">
            <label>Időtartam (perc)</label>
            <input
              type="number"
              min={draft.type === "Pihenő" ? 0 : 10}
              max="600"
              step="5"
              value={draft.duration}
              onChange={(event) => set("duration", Number(event.target.value))}
            />
          </div>
          <div className="field">
            <label>Intenzitás</label>
            <select
              value={draft.intensity}
              onChange={(event) => set("intensity", event.target.value)}
            >
              {[
                "regeneráló",
                "könnyű",
                "könnyű–közepes",
                "közepes",
                "közepes–magas",
                "magas",
              ].map((level) => (
                <option key={level}>{level}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Cél RPE</label>
            <input
              type="range"
              min="1"
              max="10"
              value={draft.rpe}
              onChange={(event) => set("rpe", Number(event.target.value))}
            />
            <small>{draft.rpe}/10</small>
          </div>
          <div className="field">
            <label>Edzés célja</label>
            <input
              value={draft.purpose}
              maxLength="500"
              onChange={(event) => set("purpose", event.target.value)}
              placeholder="Például: aerob alap"
            />
          </div>
          <div className="field wide">
            <label>Garmin-aktivitás kézi párosítása</label>
            <select
              value={draft.matchedActivityId || ""}
              onChange={(event) => set("matchedActivityId", event.target.value)}
            >
              <option value="">Automatikus párosítás használata</option>
              {activities.map((activity) => (
                <option key={activity.id} value={activity.id}>
                  {new Date(activity.date).toLocaleDateString("hu-HU")} ·{" "}
                  {activity.type} · {activity.name}
                </option>
              ))}
            </select>
            <small>
              Csak akkor szükséges, ha az azonos nap és edzéstípus alapján nem
              található jó egyezés.
            </small>
          </div>
          <div className="field wide">
            <label>Megjegyzés</label>
            <textarea
              value={draft.note}
              maxLength="2000"
              onChange={(event) => set("note", event.target.value)}
              placeholder="Opcionális részletek"
            />
          </div>
        </div>
        <div className="plan-editor-actions">
          {draft.id && (
            <button className="danger" onClick={() => onDelete(draft.id)}>
              <Trash2 size={15} /> Törlés
            </button>
          )}
          <span />
          <button onClick={onClose}>Mégse</button>
          <button
            className="primary"
            disabled={!valid}
            onClick={() =>
              onSave({ ...draft, id: draft.id || `plan-${Date.now()}` })
            }
          >
            Edzésterv mentése
          </button>
        </div>
      </div>
    </div>
  );
}

function WeeklyTemplateEditor({ items, onSave, onClose }) {
  const [drafts, setDrafts] = useState(() =>
      items.map((item, index) => ({
        ...item,
        id: `template-${item.date}-${index}`,
        enabled: true,
      })),
    ),
    update = (index, key, value) =>
      setDrafts((current) =>
        current.map((item, itemIndex) =>
          itemIndex === index ? { ...item, [key]: value } : item,
        ),
      ),
    active = drafts.filter((item) => item.enabled),
    minutes = active.reduce((sum, item) => sum + Number(item.duration || 0), 0),
    duplicateDates = new Set(
      active
        .filter((item, index) =>
          active.some(
            (other, otherIndex) =>
              otherIndex !== index && other.date === item.date,
          ),
        )
        .map((item) => item.date),
    ),
    valid =
      active.length > 0 &&
      active.every(
        (item) =>
          item.date && item.title.trim() && !duplicateDates.has(item.date),
      );
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal template-editor"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close" onClick={onClose}>
          <X size={18} />
        </button>
        <span className="eyebrow">HETI SABLON ELŐNÉZETE</span>
        <h2>Oszd ki az edzéseket a saját hetedre</h2>
        <p>
          A javaslatot mentés előtt naponként módosíthatod. Az ütköző napokat
          pirossal jelöljük.
        </p>
        <div className="template-summary">
          <span>
            <strong>{active.length}</strong> edzés
          </span>
          <span>
            <strong>
              {Math.floor(minutes / 60)}ó {minutes % 60}p
            </strong>{" "}
            összesen
          </span>
        </div>
        <div className="template-list">
          {drafts.map((item, index) => (
            <div
              className={`template-row ${item.enabled ? "" : "disabled"} ${duplicateDates.has(item.date) ? "invalid" : ""}`}
              key={item.id}
            >
              <label className="template-toggle">
                <input
                  type="checkbox"
                  checked={item.enabled}
                  onChange={(event) =>
                    update(index, "enabled", event.target.checked)
                  }
                />
                <span>{item.enabled ? "Aktív" : "Kihagyva"}</span>
              </label>
              <input
                aria-label={`${index + 1}. edzés napja`}
                type="date"
                value={item.date}
                disabled={!item.enabled}
                onChange={(event) => update(index, "date", event.target.value)}
              />
              <select
                aria-label={`${index + 1}. edzés típusa`}
                value={item.type}
                disabled={!item.enabled}
                onChange={(event) => update(index, "type", event.target.value)}
              >
                {[
                  "Kardió",
                  "Erő",
                  "Futás",
                  "Túrázás",
                  "Kerékpár",
                  "Mobilitás",
                  "Pihenő",
                ].map((type) => (
                  <option key={type}>{type}</option>
                ))}
              </select>
              <input
                aria-label={`${index + 1}. edzés neve`}
                value={item.title}
                disabled={!item.enabled}
                onChange={(event) => update(index, "title", event.target.value)}
              />
              <label className="template-duration">
                <input
                  aria-label={`${index + 1}. edzés időtartama`}
                  type="number"
                  min="0"
                  max="600"
                  step="5"
                  value={item.duration}
                  disabled={!item.enabled}
                  onChange={(event) =>
                    update(index, "duration", Number(event.target.value))
                  }
                />
                <span>perc</span>
              </label>
              {duplicateDates.has(item.date) && (
                <small>Erre a napra már került edzés.</small>
              )}
            </div>
          ))}
        </div>
        <div className="template-editor-actions">
          <button onClick={onClose}>Mégse</button>
          <button
            className="primary"
            disabled={!valid}
            onClick={() => onSave(active.map(({ enabled, ...item }) => item))}
          >
            Heti terv mentése
          </button>
        </div>
      </div>
    </div>
  );
}

const shiftIsoDate = (value, days) => {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + Number(days));
  return isoDate(date);
};
function BatchMoveEditor({ plans, onSave, onClose }) {
  const sorted = [...plans].sort((a, b) => a.date.localeCompare(b.date)),
    [selected, setSelected] = useState(
      () => new Set(sorted.map((item) => item.id)),
    ),
    [offset, setOffset] = useState(1),
    toggle = (id) =>
      setSelected((current) => {
        const next = new Set(current);
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
      }),
    moved = sorted
      .filter((item) => selected.has(item.id))
      .map((item) => ({ ...item, date: shiftIsoDate(item.date, offset) })),
    stationaryDates = new Set(
      sorted.filter((item) => !selected.has(item.id)).map((item) => item.date),
    ),
    movedDates = moved.map((item) => item.date),
    conflicts = new Set(
      movedDates.filter(
        (date, index) =>
          stationaryDates.has(date) || movedDates.indexOf(date) !== index,
      ),
    ),
    valid = selected.size > 0 && offset !== 0 && conflicts.size === 0;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal batch-move-editor"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close" onClick={onClose}>
          <X size={18} />
        </button>
        <span className="eyebrow">CSOPORTOS TERVMÓDOSÍTÁS</span>
        <h2>Több edzés együttes mozgatása</h2>
        <p>
          A kijelölt edzéseket azonos számú nappal toljuk el, ezért a köztük
          lévő ritmus változatlan marad.
        </p>
        <div className="batch-controls">
          <button
            onClick={() => setSelected(new Set(sorted.map((item) => item.id)))}
          >
            Mind kijelölése
          </button>
          <button onClick={() => setSelected(new Set())}>
            Kijelölés törlése
          </button>
          <label>
            <span>Eltolás napokban</span>
            <input
              aria-label="Eltolás napokban"
              type="number"
              min="-30"
              max="30"
              value={offset}
              onChange={(event) =>
                setOffset(
                  Math.max(-30, Math.min(30, Number(event.target.value))),
                )
              }
            />
          </label>
        </div>
        <div className="batch-list">
          {sorted.map((item) => {
            const active = selected.has(item.id),
              nextDate = active ? shiftIsoDate(item.date, offset) : item.date,
              conflict = active && conflicts.has(nextDate);
            return (
              <label
                className={`batch-row ${active ? "selected" : ""} ${conflict ? "invalid" : ""}`}
                key={item.id}
              >
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggle(item.id)}
                />
                <span>
                  <b>{item.title}</b>
                  <small>
                    {item.type} · {item.duration} perc
                  </small>
                </span>
                <time>
                  {new Date(`${item.date}T12:00:00`).toLocaleDateString(
                    "hu-HU",
                    { month: "short", day: "numeric" },
                  )}
                </time>
                <ChevronRight size={16} />
                <time>
                  {new Date(`${nextDate}T12:00:00`).toLocaleDateString(
                    "hu-HU",
                    { month: "short", day: "numeric" },
                  )}
                </time>
                {conflict && <em>Napütközés</em>}
              </label>
            );
          })}
        </div>
        <div className="batch-feedback">
          {conflicts.size ? (
            <span className="error">
              Oldd fel a napütközéseket az eltolás vagy a kijelölés
              módosításával.
            </span>
          ) : (
            <span>
              {selected.size} edzés{" "}
              {offset > 0
                ? `${offset} nappal későbbre`
                : offset < 0
                  ? `${Math.abs(offset)} nappal korábbra`
                  : "változatlan dátummal"}{" "}
              kerül.
            </span>
          )}
        </div>
        <div className="template-editor-actions">
          <button onClick={onClose}>Mégse</button>
          <button
            className="primary"
            disabled={!valid}
            onClick={() => onSave(moved)}
          >
            Kijelölt edzések mozgatása
          </button>
        </div>
      </div>
    </div>
  );
}

function PersistentCalendarPage({ profile, cloudState, onCloudPatch }) {
  const data = useDashboardData(),
    activities = data?.sessions || [],
    today = data?.today || isoDate(new Date()),
    anchor = new Date(`${today}T12:00:00`),
    [month, setMonth] = useState(
      () => new Date(anchor.getFullYear(), anchor.getMonth(), 1),
    ),
    [selected, setSelected] = useState(() => isoDate(anchor)),
    [editor, setEditor] = useState(null),
    [templateEditor, setTemplateEditor] = useState(false),
    [batchEditor, setBatchEditor] = useState(false),
    plans = cloudState?.plans || [],
    planned = plans.reduce((map, item) => map.set(item.date, [...(map.get(item.date) || []), item]), new Map()),
    actual = activities.reduce((map, item) => {
      const normalized = {...item,title:item.name,duration:item.durationMin,status:"done"};
      return map.set(item.date, [...(map.get(item.date) || []), normalized]);
    }, new Map());
  const first = new Date(month.getFullYear(), month.getMonth(), 1),
    gridStart = new Date(first);
  gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const cells = Array.from({ length: 42 }, (_, index) => {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + index);
      const key = isoDate(date),
        items = [...(actual.get(key) || []), ...(planned.get(key) || [])];
      return { date, key, items, item:items[0], current: date.getMonth() === month.getMonth() };
    }),
    selectedPlans = planned.get(selected) || [],
    selectedActuals = actual.get(selected) || [],
    selectedItems = [...selectedActuals, ...selectedPlans],
    selectedPlan = selectedPlans[0],
    selectedActual = selectedActuals[0],
    selectedItem = selectedItems[0],
    comparison = selectedPlan
      ? evaluatePlan(selectedPlan, activities, today)
      : null,
    selectedDate = new Date(`${selected}T12:00:00`),
    monthLabel = month.toLocaleDateString("hu-HU", {
      year: "numeric",
      month: "long",
    }),
    shift = (value) =>
      setMonth(
        (current) =>
          new Date(current.getFullYear(), current.getMonth() + value, 1),
      ),
    save = (plan) => {
      onCloudPatch({ plan });
      setSelected(plan.date);
      setEditor(null);
    },
    remove = (id) => {
      onCloudPatch({ deletePlan: id });
      setEditor(null);
    },
    template = buildPersonalWeek(profile, data),
    saveTemplate = (items) => {
      onCloudPatch({ plans: items });
      setTemplateEditor(false);
      if (items[0]) setSelected(items[0].date);
    },
    saveBatch = (items) => {
      onCloudPatch({ plans: items });
      setBatchEditor(false);
      if (items[0]) setSelected(items[0].date);
    };
  return (
    <>
      <PageHeader eyebrow="SZEMÉLYES HETI TERV" title="Terv és tény">
        <div className="calendar-actions">
          <button aria-label="Előző hónap" onClick={() => shift(-1)}>
            <ChevronLeft size={14} />
          </button>
          <b>{monthLabel}</b>
          <button aria-label="Következő hónap" onClick={() => shift(1)}>
            <ChevronRight size={14} />
          </button>
          <button
            className="calendar-new"
            onClick={() => setEditor(emptyPlan(selected))}
          >
            <Plus size={15} /> ÚJ EDZÉS
          </button>
        </div>
      </PageHeader>
      <div className="calendar-toolbar">
        <div className="calendar-legend">
          <span>
            <i className="planned" />
            TERVEZETT
          </span>
          <span>
            <i className="done" />
            TELJESÍTETT
          </span>
          <span>
            <i className="extra" />
            GARMIN ELŐZMÉNY
          </span>
        </div>
        <div className="calendar-toolbar-actions">
          <button
            disabled={plans.length < 2}
            onClick={() => setBatchEditor(true)}
          >
            TÖBB EDZÉS MOZGATÁSA
          </button>
          <button onClick={() => setTemplateEditor(true)}>
            HETI SABLON SZEMÉLYRE SZABÁSA
          </button>
        </div>
      </div>
      <section className="calendar card">
        <div className="weekdays">
          {[
            "HÉTFŐ",
            "KEDD",
            "SZERDA",
            "CSÜTÖRTÖK",
            "PÉNTEK",
            "SZOMBAT",
            "VASÁRNAP",
          ].map((day) => (
            <b key={day}>{day}</b>
          ))}
        </div>
        <div className="calendar-grid">
          {cells.map((cell) => (
            <button
              key={cell.key}
              className={`${cell.key === selected ? "selected" : ""} ${!cell.current ? "outside" : ""}`}
              onClick={() => setSelected(cell.key)}
            >
              <span>{cell.date.getDate()}</span>
              {cell.item && (
                <div className={cell.item.status}>
                  <Activity size={13} />
                  <b>{cell.item.type}</b>
                  <small>
                    {cell.items.length > 1 ? `${cell.items.length} edzés · ${cell.items.reduce((sum,item)=>sum+Number(item.duration||0),0)}p` : `${cell.item.title} · ${cell.item.duration}p`}
                  </small>
                </div>
              )}
            </button>
          ))}
        </div>
      </section>
      <div className="calendar-detail card">
        <div>
          <span className="eyebrow">KIVÁLASZTOTT NAP</span>
          <h2>
            {selectedDate.toLocaleDateString("hu-HU", {
              month: "long",
              day: "numeric",
            })}
          </h2>
        </div>
        <div>
          <div className="selected-day-sessions">
            {selectedItems.length
              ? selectedItems.map(item=><p key={item.id||`${item.title}-${item.duration}`}><b>{item.title}</b> · {item.duration} perc · {item.status==="done" ? "Garmin-adat" : "személyes terv"}</p>)
              : selectedDate.getDay() === 0 ||
                  dayCodes[selectedDate.getDay()] === profile.restDay
                ? "Tervezett pihenőnap."
                : "Nincs edzés erre a napra."}
          </div>
          {comparison && (
            <div
              className={`plan-comparison ${comparison.status.replaceAll(" ", "-")}`}
            >
              <b>{comparison.status.toUpperCase()}</b>
              {comparison.activity && (
                <span>
                  {comparison.method} párosítás · tény{" "}
                  {comparison.activity.durationMin} perc · eltérés{" "}
                  {comparison.difference > 0 ? "+" : ""}
                  {comparison.difference} perc
                </span>
              )}
            </div>
          )}
        </div>
        <div className="calendar-detail-actions">
          {selectedPlan && (
            <button onClick={() => setEditor(selectedPlan)}>
              <Pencil size={14} /> SZERKESZTÉS ÉS PÁROSÍTÁS
            </button>
          )}
          <button
            className="primary"
            onClick={() => setEditor(emptyPlan(selected))}
          >
            <Plus size={14} /> EDZÉS HOZZÁADÁSA
          </button>
        </div>
      </div>
      {editor && (
        <PlanEditor
          value={editor}
          activities={activities}
          onSave={save}
          onDelete={remove}
          onClose={() => setEditor(null)}
        />
      )}{" "}
      {templateEditor && (
        <WeeklyTemplateEditor
          items={template}
          onSave={saveTemplate}
          onClose={() => setTemplateEditor(false)}
        />
      )}{" "}
      {batchEditor && (
        <BatchMoveEditor
          plans={plans}
          onSave={saveBatch}
          onClose={() => setBatchEditor(false)}
        />
      )}
    </>
  );
}

function OverviewPage({ profile }) {
  const data = useDashboardData(),
    [range, setRange] = useState(90),
    sessions = data?.sessions || [],
    anchor = data?.today ? new Date(`${data.today}T23:59:59`) : new Date(),
    from = new Date(anchor);
  from.setDate(from.getDate() - range + 1);
  const visible = sessions.filter((item) => new Date(item.date) >= from),
    minutes = visible.reduce((sum, item) => sum + Number(item.durationMin || 0), 0),
    load = visible.reduce((sum, item) => sum + Number(item.load || 0), 0),
    strength = visible.filter((item) => item.type === "Erő").length,
    cardio = visible.filter((item) => item.type !== "Erő").length,
    trendLimit = range === 30 ? 5 : range === 90 ? 13 : 52,
    points = (data?.trends || trendData).slice(-trendLimit).map((item, index) => ({
      ...item,
      label: item.date
        ? new Date(item.date).toLocaleDateString("hu-HU", { month: "short", day: "numeric" })
        : item.week || `${index + 1}. hét`,
    }));
  return <><PageHeader eyebrow="TELJESÍTMÉNYKÉP" title="Áttekintés"><div className="segmented">{[[30,"30 nap"],[90,"90 nap"],[365,"1 év"]].map(([value,label])=><button key={value} className={range===value?"active":""} onClick={()=>setRange(value)}>{label}</button>)}</div></PageHeader><section className="overview-kpis">{[[visible.length,"EDZÉS"],[`${Math.floor(minutes/60)} ó ${minutes%60} p`,"EDZÉSIDŐ"],[load.toLocaleString("hu-HU"),"ÖSSZTERHELÉS"],[data?.readiness??"—","MAI TERHELHETŐSÉG"]].map(([value,label])=><div className="card" key={label}><strong>{value}</strong><span>{label}</span></div>)}</section><section className="card overview-chart"><div className="section-head"><div><span className="eyebrow">FEJLŐDÉSTÖRTÉNET</span><h2>Edzettség, fáradtság és forma</h2></div><small>{range===365?"1 ÉV":`${range} NAP`}</small></div><ResponsiveContainer width="100%" height={330}><LineChart data={points}><CartesianGrid stroke="#2a2b2b" vertical={false}/><XAxis dataKey="label" stroke="#747776"/><YAxis stroke="#747776"/><Tooltip contentStyle={{background:"#181a19",border:"1px solid #343635"}}/><Line type="monotone" dataKey="ctl" name="Hosszú távú edzettség" stroke="var(--accent)" strokeWidth={3} dot={false}/><Line type="monotone" dataKey="atl" name="Rövid távú fáradtság" stroke="#f59e0b" strokeWidth={2} dot={false}/><Line type="monotone" dataKey="tsb" name="Forma" stroke="#3b82f6" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></section><section className="overview-bottom"><div className="card"><span className="eyebrow">EDZÉSMEGOSZLÁS</span><h2>{strength} erőedzés · {cardio} egyéb edzés</h2><p>A kiválasztott időszak minden Garmin-edzése szerepel az összesítésben, az azonos napon végzett több edzést is külön számoljuk.</p></div><div className="card"><span className="eyebrow">SZEMÉLYES CÉL</span><h2>{profile.goal}</h2><p>Heti {profile.weeklyHours} órás keret · {profile.strengthRatio}% erőedzés-cél.</p></div></section></>;
}

export function App() {
  const [collapsed, setCollapsed] = useState(false),
    [active, setActive] = useState("Áttekintés"),
    [accent, setAccent] = useState(
      () => localStorage.getItem("hybrid-accent") || "teal",
    ),
    [profile, setProfile] = useState(readProfile),
    [onboarded, setOnboarded] = useState(
      () => localStorage.getItem("hybrid-onboarding-version") === "2",
    ),
    [cloudState, setCloudState] = useState(null),
    [showSplash, setShowSplash] = useState(
      () => forceSplashPreview() || !splashWasShown(),
    ),
    [user, setUser] = useState(null),
    [authReady, setAuthReady] = useState(false),
    [garminStatus, setGarminStatus] = useState(null);
  const applyAccent = (value) => {
    const option =
        accentOptions.find((x) => x.id === value) || accentOptions[0],
      root = document.documentElement;
    setAccent(option.id);
    localStorage.setItem("hybrid-accent", option.id);
    root.style.setProperty("--accent", option.color);
    root.style.setProperty("--accent-soft", option.soft);
    root.style.setProperty("--accent-deep", option.deep);
    root.style.setProperty("--accent-text", option.text);
  };
  const saveProfile = (value) => {
    const normalized = { ...defaultProfile, ...value };
    setProfile(normalized);
    localStorage.setItem("hybrid-profile", JSON.stringify(normalized));
  };
  const saveCloudPatch = (patch) => {
    setCloudState((current) => mergeCloudState(current, patch));
    patchCloudState(patch)
      .then(setCloudState)
      .catch(() => {});
  };
  const saveProfileCloud = (value) => {
      saveProfile(value);
      saveCloudPatch({ profile: value });
    },
    applyAccentCloud = (value) => {
      applyAccent(value);
      saveCloudPatch({ accent: value });
    };
  useEffect(() => applyAccent(accent), []);
  useEffect(() => {
    let activeRequest = true;
    fetch("/api/auth")
      .then((response) => (response.ok ? response.json() : { user: null }))
      .then((body) => {
        if (activeRequest) setUser(body.user || null);
      })
      .catch(() => {})
      .finally(() => activeRequest && setAuthReady(true));
    return () => {
      activeRequest = false;
    };
  }, []);
  useEffect(() => {
    if (!user) return;
    let activeRequest = true;
    setCloudState(null);
    fetchCloudState()
      .then((remote) => {
        if (!activeRequest) return;
        setCloudState(remote);
        if (remote.profile) {
          saveProfile(remote.profile);
          localStorage.setItem("hybrid-onboarding-version", "2");
          setOnboarded(true);
        } else {
          setProfile({ ...defaultProfile, name: user.name || "Sportoló" });
          setOnboarded(false);
        }
        if (remote.accent) applyAccent(remote.accent);
      })
      .catch(() => {});
    return () => {
      activeRequest = false;
    };
  }, [user?.id]);
  useEffect(() => {
    if (!user) return;
    fetch("/api/garmin")
      .then((response) => response.json())
      .then(setGarminStatus)
      .catch(() => setGarminStatus({ status: "disconnected" }));
  }, [user?.id]);
  const logout = async () => {
    await fetch("/api/auth", { method: "DELETE" }).catch(() => {});
    setUser(null);
    setCloudState(null);
  };
  const pages = {
    Áttekintés: <OverviewPage profile={profile} />,
    Ma: (
      <TodayLive
        profile={profile}
        cloudState={cloudState}
        onCloudPatch={saveCloudPatch}
        garminStatus={garminStatus}
        onConnect={() => setActive("Beállítások")}
      />
    ),
    Naptár: (
      <PersistentCalendarPage
        profile={profile}
        cloudState={cloudState}
        onCloudPatch={saveCloudPatch}
      />
    ),
    Trendek: <LiveTrendsPage profile={profile} />,
    Cél: (
      <GoalPage
        profile={profile}
        onEdit={() => setActive("Profil")}
        cloudState={cloudState}
        onCloudPatch={saveCloudPatch}
      />
    ),
    Elemzések: <InsightsPage profile={profile} />,
    Napló: (
      <LiveJournalPage cloudState={cloudState} onCloudPatch={saveCloudPatch} />
    ),
    Profil: <ProfilePage profile={profile} onSave={saveProfileCloud} />,
    Beállítások: (
      <SettingsPage
        accent={accent}
        onAccent={applyAccentCloud}
        profile={profile}
        onProfileSave={saveProfileCloud}
        user={user}
        onLogout={logout}
        onGarminStatus={setGarminStatus}
      />
    ),
  };
  const finishSplash = () => {
    globalThis.sessionStorage?.setItem("hybrid-splash-shown", "1");
    setShowSplash(false);
  };
  if (!authReady)
    return (
      <div className="auth-loading">
        <img src={brandMarkUrl} alt="" />
        <span>Biztonságos munkamenet ellenőrzése…</span>
      </div>
    );
  if (!user) return <AuthScreen onAuthenticated={setUser} />;
  return (
    <div className="app">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
        active={active}
        onActive={setActive}
        profile={profile}
        garminStatus={garminStatus}
      />
      <div className="content">
        {pages[active] || <Placeholder page={active} />}
      </div>
      <ExplainabilityLayer page={active} />
      <MetricHeaderLayer page={active} />
      {showSplash && onboarded && <BrandSplash onDone={finishSplash} />}{" "}
      {!onboarded && (
        <PersonalOnboarding
          profile={{ ...profile, name: user.name || profile.name }}
          accent={accent}
          onAccent={applyAccentCloud}
          onSave={saveProfileCloud}
          onDone={() => {
            localStorage.setItem("hybrid-onboarding-version", "2");
            setOnboarded(true);
          }}
        />
      )}
    </div>
  );
}
