import { JSDOM } from "jsdom";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { createServer } from "vite";

const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: "http://localhost/" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
globalThis.localStorage = dom.window.localStorage;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.SVGElement = dom.window.SVGElement;
globalThis.MutationObserver = dom.window.MutationObserver;
dom.window.HTMLElement.prototype.attachEvent = () => {};
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
const budapestDay=(offset=0)=>{const date=new Date(Date.now()+offset*86400000);return new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Budapest",year:"numeric",month:"2-digit",day:"2-digit"}).format(date)};
const TODAY=budapestDay(),YESTERDAY=budapestDay(-1),budapestToday=()=>TODAY;
const dashboardFixture={
  source:"garmin",today:TODAY,readiness:78,confidence:"magas",readinessSource:"garmin_training_readiness",garminTrainingReadiness:{score:78,level:"HIGH"},
  dataQuality:{referenceDate:TODAY,missingMetrics:["Alvás"],activityCount:461,activityDateFrom:"2024-04-01",activityDateTo:YESTERDAY,hrvStatus:"BALANCED",hrvBaselineLow:50,hrvBaselineHigh:66,officialLoadCoveragePct:92},
decision:{title:"Zone 2 alapozás",duration:"45–70 perc",intensity:"közepes",rationale:"Teszt regenerációs indoklás."},week:{total_load:420,change_pct:4,recommendations:["Tartsd a kiegyensúlyozott struktúrát."]},
  sessions:[{id:"test-activity",date:TODAY,type:"Futás",name:"Teszt Zone 2 futás",durationMin:48,avgHr:137,distanceKm:8.2,load:64}],heat:[],metrics:[],trends:[],zones:[0,48,0,0,0],
  coaching:{tips:[{key:"record",tone:"celebrate",priority:75,title:"Új egyéni csúcs: 5 km",message:"Új legjobb eredmény.",why:"A Garmin új rekordot rögzített.",action:"Ünnepeld meg."},{key:"sleep",tone:"warn",priority:75,title:"Alváshiány gyűlik",message:"Keveset aludtál.",why:"Átlag 6,1 óra.",action:"Feküdj le korábban."}],weekly:{weekStart:"2026-08-10",weekEnd:"2026-08-16",sessions:4,minutes:250,load:900,strengthMinutes:90,changePct:12,sleepHours:7.1,hrvChangePct:-3,summary:"A múlt héten 4 edzés, 4,2 óra edzésidő.",highlights:["Új egyéni csúcs: 5 km"],focus:"Feküdj le korábban."}},
  benchmarks:{profile:{sex:"male",age:35},demo:false,sources:[{key:"hunt2013",label:"HUNT 3 Fitness Study",citation:"Loe H et al. PLoS ONE 2013",url:"https://doi.org/10.1371/journal.pone.0064319",license:"CC BY 4.0"}],cards:[{key:"vo2max",title:"VO2max – aerob kapacitás",status:"ok",value:51,valueText:"51,0 ml/kg/perc",percentile:60,atLeast:false,level:2,category:"jó",cohort:"30–39 éves férfiak",headline:"Jobb, mint a veled egykorú férfiak kb. 60%-áé.",detail:"Referencia.",trend:null,nextGoal:"+4,4 ml/kg/perc kell a „kiváló” szinthez (80. percentilis).",confidence:"közepes",caveat:"Becsült érték.",sources:["hunt2013"]},{key:"steps",title:"Napi lépésszám",status:"missing",headline:"Nincs napi lépésszám adat.",valueText:"—",percentile:null,level:null,category:null,confidence:null,sources:["hunt2013"]}]}
};
const cloudPatches=[];
let syncResponseMode="non-json",syncRequests=[];
let dashboardAvailable=false;
let assistantState={consent:false,memoryEnabled:true,memory:[],conversation:[],usage:{questions:0,limit:15,remaining:15,tokenBudgetLeft:true}};
const assistantCalls=[];
let mockedCloudState={version:2,profile:null,accent:"teal",checkins:{},feedback:{},plans:[]};
globalThis.fetch = async (input,options={}) => {
  const url=String(input);
  if(url.endsWith("/api/assistant")){
    if(options.method==="POST"){const payload=JSON.parse(options.body);assistantCalls.push(payload);
      if(payload.action==="consent")assistantState={...assistantState,consent:payload.value};
      if(payload.action==="ask")assistantState={...assistantState,conversation:[...assistantState.conversation,{role:"user",content:payload.question},{role:"assistant",content:"**Ma** könnyű nap.\n\n- Zone 2 futás 40 perc\n- Nyújtás"}],memory:[{id:"m1",text:"Este edz."}],usage:{...assistantState.usage,questions:1,remaining:14}};
      if(payload.action==="deleteMemory")assistantState={...assistantState,memory:[]};}
    return {ok:true,status:200,json:async()=>({...assistantState,answer:"ok"}),text:async()=>""};
  }
  if(url.endsWith("/api/dashboard")&&!dashboardAvailable)return {ok:false,status:404,json:async()=>({error:"Még nincs szinkronizált Garmin-adat.",code:"no_dashboard_data"}),text:async()=>JSON.stringify({error:"Még nincs szinkronizált Garmin-adat.",code:"no_dashboard_data"})};
  if(url.endsWith("/api/model"))return {ok:true,status:200,json:async()=>({active:{id:7,trained_at:"2026-09-22T03:15:00+00:00",data_start:"2025-09-01",data_end:"2026-09-21",samples:340,model_mae:0.42,baseline_mae:0.61,eligible:true,active:true,promotion_reason:"A jelölt MAE-je jobb.",validation:{improvementPct:31.1,windowsWon:3,windowCount:3}},latest:null,readiness:{availableSamples:340,requiredSamples:132,progressPct:100,observedDays:365,dataStart:"2025-09-01",dataEnd:"2026-09-22",readyForValidation:true,coverage:[{key:"sleep_score",label:"Alváspontszám",availableDays:350,coveragePct:96},{key:"hrv",label:"Éjszakai HRV",availableDays:340,coveragePct:93},{key:"resting_hr",label:"Nyugalmi pulzus",availableDays:355,coveragePct:97},{key:"hybrid_load",label:"Edzésterhelés",availableDays:365,coveragePct:100},{key:"session_rpe",label:"Saját edzésérzet (RPE)",availableDays:40,coveragePct:11}]},schedule:{nextCheckAt:"2026-09-23T03:15:00+00:00",frequency:"daily"},lastRun:{checkedAt:"2026-09-22T03:15:00+00:00",status:"candidate_ready",due:true,reasons:["30 új adatnap érkezett"],dataEnd:"2026-09-22",message:"A validált jelölt aktiválva."}}),text:async()=>""};
  if(url.endsWith("/api/auth"))return {ok:true,status:200,json:async()=>({user:{id:"test-user",email:"attilla@example.com",name:"Attila"}}),text:async()=>""};
  if(url.endsWith("/api/garmin"))return {ok:true,status:200,json:async()=>({status:"connected",email_hint:"at••••@example.com"}),text:async()=>""};
  if(url.endsWith("/api/sync")){
    if(syncResponseMode==="failed"){
      syncRequests.push(options.body||"");
      const body={run_id:"resume-test",status:"failed",phase:"failed",progress:42,resumable:true,message:"A Garmin többszöri automatikus próbálkozás után sem válaszolt."};
      return {ok:false,status:409,json:async()=>body,text:async()=>JSON.stringify(body)};
    }
    return {ok:false,status:404,text:async()=>"The page could not be found"};
  }
  if(url.endsWith("/api/state")){
    if(options.method==="PATCH"){
      const patch=JSON.parse(options.body);cloudPatches.push(patch);
      if(patch.profile)mockedCloudState.profile=patch.profile;
      if(patch.accent)mockedCloudState.accent=patch.accent;
      if(patch.checkin)mockedCloudState.checkins[patch.checkin.date]=patch.checkin.value;
      if(patch.feedback)mockedCloudState.feedback[patch.feedback.activityId]=patch.feedback.value;
      if(patch.plan)mockedCloudState.plans=[...mockedCloudState.plans.filter(item=>item.id!==patch.plan.id),patch.plan];
      if(patch.plans){const replaceDates=new Set(patch.replacePlanDates||[]),byId=new Map(mockedCloudState.plans.filter(item=>!replaceDates.has(item.date)).map(item=>[item.id,item]));patch.plans.forEach(item=>byId.set(item.id,item));mockedCloudState.plans=[...byId.values()];} // same id-based merge as user_state.apply_patch
      if(patch.deletePlan)mockedCloudState.plans=mockedCloudState.plans.filter(item=>item.id!==patch.deletePlan);
    }
    return {ok:true,status:200,json:async()=>mockedCloudState,text:async()=>JSON.stringify(mockedCloudState)};
  }
  return {ok:true,status:200,json:async()=>dashboardFixture,text:async()=>JSON.stringify(dashboardFixture)};
};
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
localStorage.setItem("hybrid-onboarding-version", "2");

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", optimizeDeps: { noDiscovery: true } });
try {
  const { App } = await vite.ssrLoadModule("/src/App.jsx");
  const gateRoot = createRoot(document.getElementById("root"));
  await act(async () => gateRoot.render(React.createElement(App)));
  await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
  if (!document.querySelector(".content")?.textContent.includes("Első Garmin-szinkron")) throw new Error("Szinkronizált adat nélkül nem a szinkronkapu jelent meg.");
  const lockedNav=[...document.querySelectorAll(".sidebar nav button.locked")];
  if (lockedNav.map(node=>node.textContent.trim()).join(",")!=="Áttekintés,Naptár,Trendek,Cél,Insights,Hol tartasz?,Napló"||!lockedNav.every(node=>node.disabled)) throw new Error("Hibás zárolt menüpontok: "+lockedNav.map(node=>node.textContent.trim()).join(","));
  if (document.querySelector(".sync-gate-action .primary")?.disabled) throw new Error("Csatlakoztatott Garmin-fióknál a szinkron gomb nem indítható.");
  if (!document.querySelector(".sidebar .profile")?.textContent.includes("Garmin csatlakoztatva")) throw new Error("Az oldalsáv nem a valós Garmin-állapotot mutatja.");
  await act(async () => gateRoot.unmount());
  dashboardAvailable=true;
  console.log("OK adatfüggő oldalak zárolása az első szinkronig");
  const root = createRoot(document.getElementById("root"));
  await act(async () => root.render(React.createElement(App)));
  const bundledLogo=document.querySelector('.brand-logo img');
  if (!bundledLogo?.getAttribute("src")||bundledLogo.getAttribute("src")==="[object Object]") throw new Error("A bundle-ölt Hybrid Athlete logó hiányzik.");
  await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
  const longDay=new Date(`${TODAY}T12:00:00`).toLocaleDateString("hu-HU",{month:"long"});
  if (!document.querySelector(".content header")?.textContent.includes(longDay)) throw new Error("A napi állapotfelmérés dátuma nem magyar, közérthető formátumban jelenik meg.");
  if (document.querySelector(".decision-card")) throw new Error("A napi javaslat az állapotfelmérés előtt megjelent.");
  const scaleRows=[...document.querySelectorAll(".checkin-gate .scale-row")];
  if (scaleRows.length!==4||!scaleRows[0].textContent.includes("1 · nincs")||!scaleRows[1].textContent.includes("5 · kimerült vagyok")||!scaleRows[2].textContent.includes("1 · nincs kedvem")||!scaleRows[3].textContent.includes("5 · nagyon feszült vagyok")) throw new Error("Az állapotfelmérés 1–5 skáláinak közérthető végpontjai hiányoznak.");
  const gateSave=[...document.querySelectorAll(".checkin-gate button")].find(node=>node.textContent.includes("javaslat kiszámítása"));
  if (!gateSave?.disabled) throw new Error("Hiányos állapotfelméréssel is kérhető volt javaslat.");
  for (const row of scaleRows) {
    const first=row.querySelector("button");
    if(first.getAttribute("aria-pressed")!=="false"||!first.getAttribute("aria-label")?.includes("1 az 5-ből")) throw new Error("Az állapotfelmérés választógombjai nem hozzáférhetők.");
    await act(async()=>first.click());
    if(first.getAttribute("aria-pressed")!=="true") throw new Error("Az állapotfelmérés kiválasztott értéke nincs jelezve a segítő technológiáknak.");
  }
  if (!document.querySelector(".check-alert-help")?.textContent.includes("pihenőnapra")) throw new Error("A fájdalom- és betegségjelzés következménye nincs elmagyarázva.");
  await act(async()=>gateSave.click());
  await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
  if (!document.querySelector(".decision-card")) throw new Error("A kitöltött állapotfelmérés után nem jelent meg a napi javaslat.");
  console.log("OK kötelező, közérthető és hozzáférhető napi állapotfelmérés");
  const explainedKpi=document.querySelector('.week-stats>div.explained-value');
  if (!explainedKpi?.dataset.explanation?.includes("regenerációs igényt")) throw new Error("A laikus mérőszám-magyarázat nem épült fel.");
  if (explainedKpi.getAttribute("tabindex")!=="0") throw new Error("A mérőszám-magyarázat nem érhető el billentyűzettel.");
  console.log("OK desktop logó és laikus mérőszám-magyarázat");
  await act(async () => new Promise(resolve=>setTimeout(resolve,25)));
  const readinessMetric=document.querySelector('.metric-wrap .metric');
  if (!readinessMetric) throw new Error("A readiness mérőszámsor nem jelent meg.");
  if (readinessMetric.classList.contains("explained-value")) throw new Error("A lenyitható readiness soron felesleges hover tooltip maradt.");
  await act(async () => readinessMetric.click());
  if (!document.querySelector('.metric-detail')?.textContent.includes("MIT JELENT MOST?")) throw new Error("A readiness részletes értelmezése nem nyitható meg.");
  if (!document.querySelector('.metric-detail')?.textContent.includes("ADATMINŐSÉG")) throw new Error("A readiness adatminőségi magyarázata hiányzik.");
  const coverage=document.querySelector(".data-coverage")?.textContent||"";
  for (const expected of ["Garmin Training Readiness · 78 / 100","kiegyensúlyozott · alapsáv 50–66 ms","3 / 4 elérhető","Hiányzik: Alvás","92% Garmin-adat","461 edzés"]) if (!coverage.includes(expected)) throw new Error(`Az adatlefedettségből hiányzik: ${expected}`);
  if (!document.querySelector(".decision-card")?.textContent.includes("GARMIN TRAINING READINESS")) throw new Error("A döntéskártya nem jelzi a Garmin Training Readiness forrást.");
  console.log("OK readiness részletek és adatminőség");
  const tips=[...document.querySelectorAll(".coaching-tip")];
  if (tips.length!==2||!tips[0].classList.contains("tone-celebrate")) throw new Error("A tippek nem jelentek meg a Ma oldalon.");
  await act(async()=>tips[1].querySelector("summary").click());
  if (!tips[1].open||!tips[1].textContent.includes("MIT TEGYÉL?Feküdj le korábban.")) throw new Error("A tipp indoklása nem nyitható le.");
  if (!document.querySelector(".coaching-subhead")) throw new Error("A célhoz kötött jelzések eltűntek.");
  console.log("OK szabályalapú tippek a Ma oldalon");
  const launcher=document.querySelector(".assistant-launcher");
  if (!launcher) throw new Error("Hiányzik az edzőtárs indítógombja.");
  await act(async()=>launcher.click());
  await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));
  const consent=[...document.querySelectorAll(".assistant-consent button")].find(node=>node.textContent.includes("Elfogadom"));
  if (!consent||!document.querySelector(".assistant-consent")?.textContent.includes("összesített")) throw new Error("A hozzájárulási lépés hiányzik.");
  await act(async()=>consent.click());
  const starter=[...document.querySelectorAll(".assistant-starters button")].find(node=>node.textContent==="Mit eddzek holnap?");
  await act(async()=>starter.click());
  await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));
  const reply=document.querySelector(".assistant-message.assistant");
  if (!reply?.querySelector("b")||reply.querySelectorAll("li").length!==2) throw new Error("A válasz nem jelent meg formázva.");
  if (!document.querySelector(".assistant-head small")?.textContent.includes("14/15")) throw new Error("A napi keret nem frissült.");
  if (!assistantCalls.some(call=>call.action==="ask"&&call.question==="Mit eddzek holnap?")) throw new Error("A kérdés nem ment el.");
  await act(async()=>document.querySelector('.assistant-head-actions button[title="Memória"]').click());
  if (!document.querySelector(".assistant-memory")?.textContent.includes("Este edz.")) throw new Error("A memória nem látható.");
  await act(async()=>document.querySelector(".assistant-memory li button").click());
  if (!assistantCalls.some(call=>call.action==="deleteMemory"&&call.id==="m1")) throw new Error("A memóriapont nem törölhető.");
  await act(async()=>document.querySelector('.assistant-head-actions button[aria-label="Bezárás"]').click());
  console.log("OK edzőtárs chat: hozzájárulás, kérdés, keret, memória");
  const sync = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "SZINKRON");
  await act(async () => sync.click());
  if (!document.querySelector(".header-actions")?.textContent.includes("Az online Garmin-szinkron még nincs bekötve")) throw new Error("A nem JSON szinkronhiba nem kapott érthető üzenetet.");
  console.log("OK online szinkronhiba kezelése");
  syncResponseMode="failed";
  await act(async () => [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "SZINKRON").click());
  const resume=[...document.querySelectorAll("button")].find(node=>node.textContent.trim()==="SZINKRON FOLYTATÁSA");
  if (!resume) throw new Error("A megszakadt szinkron nem folytatható ugyanabból a futásból.");
  await act(async () => resume.click());
  if (!syncRequests.some(body=>body.includes("resume-test"))) throw new Error("A folytatás nem a megszakadt futás azonosítójával indult.");
  syncResponseMode="non-json";
  console.log("OK megszakadt szinkron folytatása");
  const illness = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Betegségérzetem van");
  if (!illness) throw new Error("Hiányzik a betegségérzet check-in vezérlője.");
  if (illness.getAttribute("aria-pressed")!=="false") throw new Error("A betegségjelzés állapota nem hozzáférhető.");
  await act(async () => illness.click());
  if (illness.getAttribute("aria-pressed")!=="true") throw new Error("A betegségjelzés aktív állapota nem hozzáférhető.");
  const saveCheckin = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Mentés és a javaslat kiszámítása");
  await act(async () => saveCheckin.click());
  if (!document.querySelector(".decision-copy")?.textContent.includes("Teljes pihenő")) throw new Error("A betegségérzet nem írta felül biztonságosan az ajánlást.");
  if (![...Array(localStorage.length).keys()].map(index=>localStorage.key(index)).some(key=>key?.startsWith("hybrid-checkin-"))) throw new Error("A napi check-in nem mentődött el.");
  if (!cloudPatches.some(patch=>patch.checkin?.date===TODAY)) throw new Error("A napi check-in nem indított Neon-mentést.");
  console.log("OK napi check-in és biztonsági felülírás");
  for (const label of ["Áttekintés", "Naptár", "Trendek", "Cél", "Insights", "Hol tartasz?", "Napló", "Profil", "Beállítások"]) {
    const button = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === label);
    if (!button) throw new Error(`Hiányzó navigációs gomb: ${label}`);
    await act(async () => button.click());
    const content = document.querySelector(".content")?.textContent || "";
    if (!content.includes(label === "Áttekintés" ? "TELJESÍTMÉNYKÉP" : label === "Insights" ? "Mi működik nálam" : label === "Cél" ? "Felkészültség" : label === "Napló" ? "Edzések" : label === "Naptár" ? "Terv és tény" : label === "Trendek" ? "Terhelés és forma" : label === "Hol tartasz?" ? "Kivel hasonlítunk?" : label)) {
      throw new Error(`A(z) ${label} oldal nem renderelődött.`);
    }
    if (label === "Áttekintés") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,20)));
      const kpis=document.querySelector(".overview-kpis")?.textContent||"",quality=document.querySelector(".overview-quality")?.textContent||"";
      if (!kpis.includes("Edzések")||!document.querySelector(".overview-data-state")?.textContent.includes("Adatforrás")) throw new Error("Az Áttekintés nem a betöltött adatokat mutatja.");
      if (!quality.includes("3 / 4 elérhető")||!quality.includes("461 edzés")) throw new Error("Az Áttekintés adatminőségi és lefedettségi magyarázata hiányos.");
      if (document.querySelector(".overview-page .metric-help-icon,[aria-label*='?']")) throw new Error("Kérdőjeles jelvény maradt az Áttekintésen.");
    }
    if (label === "Trendek") {
      const translation=document.querySelector('.decision-translation');
      if(!translation?.textContent.includes('Mi változott?')||!translation.textContent.includes('Mi állhat mögötte?')||!translation.textContent.includes('Mit tehetsz?')||!translation.textContent.includes('előző 90 napból')) throw new Error("A Trendek döntéstámogató időszak-összehasonlítása hiányzik.");
      const sixtyDays=[...document.querySelectorAll('.segmented button')].find(node=>node.textContent.trim()==='60 nap');
      await act(async()=>sixtyDays.click());
      if(!document.querySelector('.decision-translation')?.textContent.includes('előző 60 napból')) throw new Error("A 60 napos időszak összehasonlítása nem frissült.");
    }
    if (label === "Insights") {
      const weeklyTranslation=document.querySelector('.decision-translation');
      if(!weeklyTranslation?.textContent.includes('A heti adatok jelentése röviden')||!weeklyTranslation.textContent.includes('Mi változott?')||!weeklyTranslation.textContent.includes('előző 7 napból')) throw new Error("Az Insights heti, közérthető értelmezése hiányzik.");
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      const modelStatus=document.querySelector('.model-status');
      if (!modelStatus?.textContent.includes("Aktív személyes regenerációs modell")) throw new Error("Az automatikus személyes modell állapota nem jelent meg.");
      if (!modelStatus.textContent.includes("átlagos abszolút hiba 0,42")||!modelStatus.textContent.includes("nem terhelhetőségi pontszám")) throw new Error("A modell pontosságának laikus magyarázata hiányzik.");
      if (!modelStatus.textContent.includes("340 / 132 nap")||!modelStatus.textContent.includes("31,1% kisebb hiba")||!modelStatus.textContent.includes("3 / 3 jobb")) throw new Error("A modell adatalkalmassági vagy validációs összefoglalója hiányzik.");
      if (!modelStatus.textContent.includes("Éjszakai HRV")||!modelStatus.textContent.includes("Következő automatikus ellenőrzés")) throw new Error("A modell adatlefedettsége vagy ütemezése hiányzik.");
      console.log("OK ütemezett személyes modellállapot, adatalkalmasság és közérthető pontosság");
    }
    if (label === "Naptár") {
      const add = [...document.querySelectorAll("button")].find(node => node.textContent.includes("EDZÉS HOZZÁADÁSA"));
      await act(async () => add.click());
      const savePlan = [...document.querySelectorAll(".plan-editor button")].find(node => node.textContent.trim() === "Edzésterv mentése");
      await act(async () => savePlan.click());
      const createdPatch=cloudPatches.find(patch=>patch.plan?.id);
      if (!createdPatch) throw new Error("Az új edzésterv nem indított Neon-mentést.");
      const edit = [...document.querySelectorAll("button")].find(node => node.textContent.includes("SZERKESZTÉS"));
      await act(async () => edit.click());
      if (!document.querySelector(".plan-editor")?.textContent.includes("Garmin-aktivitás kézi párosítása")) throw new Error("A kézi Garmin-párosítás vezérlője hiányzik.");
      await act(async () => [...document.querySelectorAll(".plan-editor button")].find(node => node.textContent.trim() === "Edzésterv mentése").click());
      if (cloudPatches.filter(patch=>patch.plan?.id===createdPatch.plan.id).length<2) throw new Error("Az edzésterv módosítása nem mentődött.");
      await act(async () => [...document.querySelectorAll("button")].find(node => node.textContent.includes("SZERKESZTÉS")).click());
      await act(async () => [...document.querySelectorAll(".plan-editor button")].find(node => node.textContent.includes("Törlés")).click());
      if (!cloudPatches.some(patch=>patch.deletePlan)) throw new Error("Az edzésterv törlése nem mentődött.");
      const template = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "HETI SABLON SZEMÉLYRE SZABÁSA");
      await act(async () => template.click());
      const templateEditor=document.querySelector(".template-editor");
      if (!templateEditor?.textContent.includes("Oszd ki az edzéseket a saját hetedre")) throw new Error("A heti sablon napkiosztási szerkesztője nem nyílt meg.");
      const firstTemplateName=templateEditor.querySelector('input[aria-label="1. edzés neve"]');
      const originalName=firstTemplateName.value;
      await act(async()=>{firstTemplateName.value=`${originalName} – egyéni`;firstTemplateName.dispatchEvent(new window.Event("input",{bubbles:true}))});
      const templateSave=[...templateEditor.querySelectorAll("button")].find(node=>node.textContent.trim()==="Heti terv mentése");
      await act(async () => templateSave.click());
      if (!cloudPatches.some(patch=>patch.plans?.length)) throw new Error("A heti sablon nem mentődött.");
      const batchMove=[...document.querySelectorAll("button")].find(node=>node.textContent.trim()==="TÖBB EDZÉS MOZGATÁSA");
      if (!batchMove||batchMove.disabled) throw new Error("A csoportos edzésmozgatás nem érhető el több tervnél.");
      await act(async()=>batchMove.click());
      const batchEditor=document.querySelector(".batch-move-editor");
      if (!batchEditor?.textContent.includes("köztük lévő ritmus változatlan marad")) throw new Error("A csoportos mozgatás magyarázata hiányzik.");
      const batchSave=[...batchEditor.querySelectorAll("button")].find(node=>node.textContent.trim()==="Kijelölt edzések mozgatása");
      const patchesBeforeMove=cloudPatches.length;
      await act(async()=>batchSave.click());
      if (cloudPatches.length<=patchesBeforeMove||!cloudPatches.at(-1)?.plans?.every(item=>item.date)) throw new Error("A csoportos dátummódosítás nem mentődött.");
      const todayNumber=String(new Date(`${budapestToday()}T12:00:00`).getDate());
      const todayCell=[...document.querySelectorAll('.calendar-grid>button')].find(node=>!node.classList.contains('outside')&&node.querySelector(':scope > span')?.textContent.trim()===todayNumber);
      if(!todayCell) throw new Error("A mai nap nem választható ki a Naptárban.");
      await act(async()=>todayCell.click());
      const addJournalPlan=[...document.querySelectorAll("button")].find(node=>node.textContent.includes("EDZÉS HOZZÁADÁSA"));
      await act(async()=>addJournalPlan.click());
      await act(async()=>[...document.querySelectorAll(".plan-editor button")].find(node=>node.textContent.trim()==="Edzésterv mentése").click());
      await act(async()=>new Promise(resolve=>setTimeout(resolve,2)));
      await act(async()=>[...document.querySelectorAll("button")].find(node=>node.textContent.includes("EDZÉS HOZZÁADÁSA")).click());
      await act(async()=>[...document.querySelectorAll(".plan-editor button")].find(node=>node.textContent.trim()==="Edzésterv mentése").click());
      const pairedSummary=[...document.querySelectorAll(".calendar-week-summary>span")].find(node=>node.textContent.includes("TERVHEZ PÁROSÍTVA"));
      if(!pairedSummary||pairedSummary.querySelector("strong")?.textContent.trim()!=="1"||!document.querySelector(".selected-actual")) throw new Error(`A heti terv–tény összesítés nem kezeli külön a napi több edzést. Párosítva: ${pairedSummary?.querySelector("strong")?.textContent.trim()||"hiányzik"}; Garmin-kártya: ${Boolean(document.querySelector(".selected-actual"))}; kiválasztott nap: ${document.querySelector(".calendar-detail h2")?.textContent.trim()||"hiányzik"}; nap tartalma: ${document.querySelector(".selected-day-sessions")?.textContent.replace(/\s+/g," ").trim()||"hiányzik"}.`);
      if(!document.querySelector('.planning-flow')?.textContent.includes('Cél')||!document.querySelector('.planning-flow')?.textContent.includes('Visszajelzés')) throw new Error("A Cél–Terv–Visszajelzés navigáció hiányzik a Naptárból.");
      await act(async()=>[...document.querySelectorAll("button")].find(node=>node.textContent.includes("NAPLÓ MEGNYITÁSA")).click());
      await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));
      if(!document.querySelector('.activity-modal')?.textContent.includes('Teszt Zone 2 futás')) throw new Error("A Naptárból nem nyílik meg közvetlenül a Garmin-edzés naplóbejegyzése.");
      await act(async()=>document.querySelector('.activity-modal .close').click());
      await act(async()=>[...document.querySelectorAll('.planning-flow button')].find(node=>node.textContent.includes('2. Terv')).click());
      if(!document.querySelector('.content')?.textContent.includes('Terv és tény')) throw new Error("A tervezési folyamatból nem lehet visszatérni a Naptárba.");
      console.log("OK edzésterv CRUD, heti sablon és csoportos mozgatás");
    }
    if (label === "Trendek") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      if (!document.querySelector('.chart-card .metric-header-explanation')?.dataset.explanation?.includes("hosszú távú edzettség")) throw new Error("A CTL/ATL/TSB grafikon laikus magyarázata hiányzik.");
      const range = [...document.querySelectorAll(".segmented button")].find(node => node.textContent.trim() === "30 nap");
      await act(async () => range.click());
      if (!range.classList.contains("active")) throw new Error("A trendek időszakváltása nem működik.");
      if (document.querySelectorAll(".trend-summary .card").length !== 5) throw new Error("Hiányoznak a fejlődéstörténet összesítői.");
      console.log("OK fejlődéstörténet és időszakváltás");
    }
    if (label === "Cél") {
      if(!document.querySelector('.planning-flow')?.querySelector('[aria-current="step"]')?.textContent.includes('Cél')) throw new Error("A tervezési folyamat nem jelöli a Cél lépést.");
      const goalScore=document.querySelector(".goal-score");
      const goalValue=Number(goalScore?.querySelector("strong")?.textContent||0);
      if (!goalScore||Number(goalScore.dataset.score)!==goalValue||!goalScore.querySelector(".recharts-responsive-container")) throw new Error("A felkészültségi kör nem a Mai döntés 0–100-as kördiagram-komponensét használja.");
      if (document.querySelectorAll(".goal-component").length !== 5) throw new Error("A felkészültségi összetevők hiányoznak.");
      const fourWeeks=[...document.querySelectorAll('.periodization-actions .segmented button')].find(node=>node.textContent.trim()==="4 hét");
      await act(async()=>fourWeeks.click());
      const preview=[...document.querySelectorAll("button")].find(node=>node.textContent.trim()==="TERV ELŐNÉZETE");
      await act(async()=>preview.click());
      const periodization=document.querySelector('.periodization-modal');
      if (!periodization||periodization.querySelectorAll('.periodization-weeks details').length!==4) throw new Error("A 4 hetes periodizációs előnézet hiányzik.");
      if (!periodization.textContent.includes("Alapozás")||!periodization.textContent.includes("Levezetés")) throw new Error("A periodizáció fázisai hiányoznak.");
      const saveCycle=[...periodization.querySelectorAll("button")].find(node=>node.textContent.trim()==="Ciklus mentése a Naptárba");
      await act(async()=>saveCycle.click());
      if (!cloudPatches.some(patch=>patch.replacePlanDates?.length&&patch.plans?.every(item=>item.id.startsWith("period-")))) throw new Error("A periodizált ciklus nem mentődött a Naptárba.");
      console.log("OK 4–12 hetes eseményspecifikus periodizáció");
      const adaptivePreview=[...document.querySelectorAll("button")].find(node=>node.textContent.trim()==="TERVJAVASLAT SZERKESZTÉSE");
      await act(async()=>adaptivePreview.click());
      const adaptiveModal=document.querySelector('.adaptive-modal');
      if (!adaptiveModal?.textContent.includes("Mi változik a következő héten?")) throw new Error("Az adaptív heti előnézet nem nyílt meg.");
      if (!adaptiveModal.querySelector('.adaptive-reasons')||!adaptiveModal.querySelector('.adaptive-comparison')) throw new Error("Az adaptív hét indoklása vagy tervösszevetése hiányzik.");
      if (!adaptiveModal.textContent.includes("Szerkeszthető heti terv")||!adaptiveModal.textContent.includes("A napi több edzés is megengedett")) throw new Error("A következő heti javaslat nem szerkeszthető vagy nem jelzi a napi több edzés lehetőségét.");
      const adaptiveDates=[...adaptiveModal.querySelectorAll('input[type="date"]')];
      if (!adaptiveDates.length||adaptiveDates.some(input=>input.value<input.min||input.value>input.max)) throw new Error("Az eseménydátum miatt a heti tervjavaslat a következő héten kívülre került.");
      const firstAdaptiveName=adaptiveModal.querySelector('input[aria-label="1. javasolt edzés neve"]');
      if (!firstAdaptiveName||firstAdaptiveName.disabled) throw new Error("Az adaptív terv edzésneve nem szerkeszthető.");
      const adaptiveRowsBefore=adaptiveModal.querySelectorAll('.adaptive-edit-row').length;
      const firstAdaptiveToggle=adaptiveModal.querySelector('.adaptive-toggle input');
      await act(async()=>firstAdaptiveToggle.click());
      if (firstAdaptiveToggle.checked||!adaptiveModal.querySelector('.adaptive-edit-row')?.textContent.includes("Kihagyva")) throw new Error("Az adaptív terv edzése nem hagyható ki.");
      const addAdaptive=[...adaptiveModal.querySelectorAll("button")].find(node=>node.textContent.includes("EDZÉS HOZZÁADÁSA"));
      await act(async()=>addAdaptive.click());
      if (adaptiveModal.querySelectorAll('.adaptive-edit-row').length!==adaptiveRowsBefore+1||!adaptiveModal.textContent.includes("Saját hozzáadás")) throw new Error("Az adaptív tervhez nem adható új edzés.");
      const saveAdaptive=[...adaptiveModal.querySelectorAll("button")].find(node=>node.textContent.trim()==="Tervjavaslat mentése a Naptárba");
      await act(async()=>saveAdaptive.click());
      if (!cloudPatches.some(patch=>patch.replacePlanDates?.length===7&&patch.plans?.length===adaptiveRowsBefore&&patch.plans?.some(item=>item.note?.includes("Saját módosítás")))) throw new Error("A szerkesztett, bővített következő hét nem mentődött.");
      if (!document.querySelector('.content')?.textContent.includes('Terv és tény')) throw new Error("A mentett heti terv után nem nyílt meg a Naptár.");
      console.log("OK heti lezárás/readiness/check-in alapú, szerkeszthető heti újratervezés");
      await act(async()=>[...document.querySelectorAll('.planning-flow button')].find(node=>node.textContent.includes('2. Terv')).click());
      if(!document.querySelector('.content')?.textContent.includes('Terv és tény')) throw new Error("A Cél oldalról nem nyitható meg a kapcsolódó edzésterv.");
      await act(async()=>[...document.querySelectorAll('.planning-flow button')].find(node=>node.textContent.includes('1. Cél')).click());
      const edit = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "CÉL SZERKESZTÉSE");
      await act(async () => edit.click());
      if (!document.querySelector(".content")?.textContent.includes("Profil")) throw new Error("A Cél oldalról nem nyitható meg a Profil.");
      console.log("OK célfelkészültség és profilszerkesztés");
    }
    if (label === "Insights") {
      const digest=document.querySelector(".weekly-digest");
      if (!digest?.textContent.includes("08.10.–08.16.")||!digest.textContent.includes("+12%")||!digest.textContent.includes("FÓKUSZ A KÖVETKEZŐ HÉTRE")) throw new Error("A heti összefoglaló hiányos.");
      console.log("OK heti összefoglaló");
    }
    if (label === "Hol tartasz?") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      const cards=[...document.querySelectorAll(".benchmark-card")];
      if (cards.length!==2||!cards[0].textContent.includes("≈ 60. percentilis")||!cards[0].querySelector(".level-chip.level-2")) throw new Error("A VO2max összevetés kártyája hiányos.");
      if (!cards[1].classList.contains("missing")||!cards[1].textContent.includes("Nincs napi lépésszám adat.")) throw new Error("A hiányzó adat nem jelenik meg érthetően.");
      if (!document.querySelector("#forras-hunt2013")?.textContent.includes("CC BY 4.0")) throw new Error("A forráslista hiányzik.");
      if (document.querySelector(".content svg.lucide-circle-help")) throw new Error("Kérdőjel-ikon került az összevetés oldalra.");
      console.log("OK forrásolt korcsoportos összevetés");
    }
    if (label === "Napló") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      if(!document.querySelector('.planning-flow')?.querySelector('[aria-current="step"]')?.textContent.includes('Visszajelzés')) throw new Error("A tervezési folyamat nem jelöli a Napló lépést.");
      const weeklyClosure=document.querySelector('.weekly-closure');
      if(!weeklyClosure?.textContent.includes('Mi teljesült?')||!weeklyClosure.textContent.includes('Mit jelez?')||!weeklyClosure.textContent.includes('Következő döntés')) throw new Error("A Napló heti lezárása vagy döntési magyarázata hiányzik.");
      const closureMetrics=[...weeklyClosure.querySelectorAll('.weekly-closure-metrics>span')];
      if(closureMetrics[0]?.querySelector('strong')?.textContent.trim()!=='1'||closureMetrics[3]?.querySelector('strong')?.textContent.trim()!=='0 / 1') throw new Error("A heti lezárás nem a külön Garmin-aktivitásokat és visszajelzéseket összesíti.");
      const planHistory=document.querySelector('.plan-outcome-history');
      if(!planHistory?.textContent.includes('Terv és tény alakulása')||!planHistory.textContent.includes('Mit tanulhatunk az eddigi hetekből?')) throw new Error("A többhetes terv–tény fejlődéstörténet hiányzik.");
      const planHistoryText=planHistory.textContent.toLowerCase();
      if(!planHistoryText.includes('x tengely:')||!planHistoryText.includes('y tengely:')||!planHistoryText.includes('edzésidő (perc)')) throw new Error("A terv–tény grafikon tengelyei vagy mértékegysége hiányzik.");
      const historyRanges=[...planHistory.querySelectorAll('.plan-history-range button')];
      if(historyRanges.map(node=>node.textContent.trim()).join('|')!=='4 HÉT|8 HÉT|12 HÉT'||!historyRanges[1].getAttribute('aria-pressed')?.includes('true')) throw new Error("A fejlődéstörténet 4/8/12 hetes szűrője hibás.");
      await act(async()=>historyRanges[0].click());
      if(historyRanges[0].getAttribute('aria-pressed')!=='true'||!planHistory.querySelector('.plan-history-table tbody tr')) throw new Error("A fejlődéstörténet időszakváltása vagy heti részletezése nem működik.");
      if(!planHistory.textContent.includes('nem bizonyít ok-okozati kapcsolatot')||!planHistory.textContent.includes('hiányzó adatokat nem tekintjük nullának')) throw new Error("A terv–tény értelmezés bizonytalansági magyarázata hiányzik.");
      if (document.querySelectorAll('.table-wrap th.metric-header-explanation').length<5) throw new Error("A Napló számoszlopainak magyarázata hiányzik.");
      const activity = document.querySelector(".activity-row");
      if (!activity) throw new Error("A Garmin-edzés nem jelent meg a naplóban.");
      if(!activity.querySelector('.plan-link.linked')?.textContent.includes('TELJESÜLT')) throw new Error("A Garmin-edzéshez kapcsolt terv állapota nem jelent meg a Naplóban.");
      await act(async () => activity.click());
      const modal = document.querySelector(".activity-modal");
      if (!modal?.textContent.includes("Teszt Zone 2 futás")) throw new Error("Az edzésrészlet nem nyílt meg.");
      if(!modal.querySelector('.activity-plan-link.matched')?.textContent.includes('Automatikus párosítás')) throw new Error("A naplóbejegyzés terv–tény magyarázata hiányzik.");
      const rpe = [...modal.querySelectorAll(".rpe-picker button")].find(node => node.textContent.trim() === "8");
      await act(async () => rpe.click());
      const save = [...modal.querySelectorAll("button")].find(node => node.textContent.trim() === "Visszajelzés mentése");
      await act(async () => save.click());
      const stored = JSON.parse(localStorage.getItem("hybrid-activity-feedback") || "{}");
      if (stored["test-activity"]?.rpe !== 8) throw new Error("Az edzés-visszajelzés nem mentődött el.");
      if (!cloudPatches.some(patch=>patch.feedback?.activityId==="test-activity"&&patch.feedback.value.rpe===8)) throw new Error("Az RPE nem indított Neon-mentést.");
      if(!document.querySelector('.weekly-closure')?.textContent.includes('1 / 1')||!document.querySelector('.weekly-closure')?.textContent.includes('8 / 10')) throw new Error("A heti lezárás nem frissült a mentett RPE-visszajelzéssel.");
      const planNextWeek=[...document.querySelectorAll('.weekly-closure button')].find(node=>node.textContent.includes('KÖVETKEZŐ HÉT TERVEZÉSE'));
      await act(async()=>planNextWeek.click());
      if (!document.querySelector('.adaptive-modal')?.textContent.includes('Szerkeszthető heti terv')) throw new Error("A heti lezárásból nem nyílik meg közvetlenül a következő heti tervjavaslat.");
      await act(async()=>document.querySelector('.adaptive-modal .close').click());
      console.log("OK edzésrészlet és RPE-visszajelzés");
    }
    if (label === "Beállítások") {
      const avatarOptions=[...document.querySelectorAll('.avatar-options button')];
      if (avatarOptions.length!==4) throw new Error("Az avatarválasztó lehetőségei hiányoznak.");
      await act(async()=>avatarOptions[1].click());
      const saveAvatar=[...document.querySelectorAll("button")].find(node=>node.textContent.trim()==="Profilkép mentése");
      await act(async()=>saveAvatar.click());
      if (!cloudPatches.some(patch=>patch.profile?.avatarPreset==="strength")) throw new Error("A kiválasztott avatar nem mentődött a profilba.");
      if (!document.querySelector('.profile .user-avatar svg')) throw new Error("A mentett avatar nem jelent meg az oldalsávban.");
      console.log("OK profilkép- és avatarbeállítás");
    }
    if (label === "Profil") {
      const saveProfile = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Profil mentése");
      await act(async () => saveProfile.click());
      if (!cloudPatches.some(patch=>patch.profile?.name==="Attila")) throw new Error("A profil nem indított Neon-mentést.");
    }
    if (label === "Beállítások") {
      const blue = [...document.querySelectorAll('[role="radio"]')].find(node => node.textContent.trim() === "Kék");
      await act(async () => blue.click());
      const saveAccent = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Választás mentése");
      await act(async () => saveAccent.click());
      if (!cloudPatches.some(patch=>patch.accent==="blue")) throw new Error("Az akcentusszín nem indított Neon-mentést.");
    }
    console.log(`OK ${label}`);
  }
  await act(async () => root.unmount());

  localStorage.clear();
  mockedCloudState={version:2,profile:null,accent:"teal",checkins:{},feedback:{},plans:[]};
  const onboardingRoot = createRoot(document.getElementById("root"));
  await act(async () => onboardingRoot.render(React.createElement(App)));
  for (let step = 1; step <= 3; step += 1) {
    const next = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Folytatás");
    if (!next) throw new Error(`Hiányzó Folytatás gomb a(z) ${step}. onboarding lépésben.`);
    await act(async () => next.click());
  }
  const finish = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Profil létrehozása");
  if (!finish) throw new Error("Hiányzó Profil létrehozása gomb.");
  await act(async () => finish.click());
  if (localStorage.getItem("hybrid-onboarding-version") !== "2") throw new Error("Az onboarding állapota nem mentődött el.");
  if (!JSON.parse(localStorage.getItem("hybrid-profile") || "null")?.name) throw new Error("A személyes profil nem mentődött el.");
  if (document.querySelector(".onboarding-backdrop")) throw new Error("Az onboarding nem zárult be.");
  console.log("OK onboarding és profilmentés");
  await act(async () => onboardingRoot.unmount());
} finally {
  await vite.close();
}
