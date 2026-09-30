import { JSDOM } from "jsdom";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { createServer } from "vite";
import { budapestToday } from "../src/overviewData.js";

const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: "http://localhost/" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
globalThis.localStorage = dom.window.localStorage;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.SVGElement = dom.window.SVGElement;
dom.window.HTMLElement.prototype.attachEvent = () => {};
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
const dashboardFixture={
  today:budapestToday(),readiness:78,confidence:"magas",decision:{title:"Zone 2 alapozás",duration:"45–70 perc",intensity:"közepes",rationale:"Teszt regenerációs indoklás."},week:{total_load:420,change_pct:4,recommendations:["Tartsd a kiegyensúlyozott struktúrát."]},
  sessions:[{id:"test-activity",date:budapestToday(),type:"Futás",name:"Teszt Zone 2 futás",durationMin:48,avgHr:137,distanceKm:8.2,load:64,loadSource:"garmin_activity_training_load"}],heat:[],metrics:[],trends:[],zones:[0,48,0,0,0],
  dataQuality:{referenceDate:budapestToday(),missingMetrics:["Garmin alváspontszám"],activityCount:461,activityDateFrom:"2024-04-01",activityDateTo:budapestToday()}
};
const cloudPatches=[];
dashboardFixture.metrics = [{name:"HRV (éjszakai)",value:"62 ms",score:75}];
let mockedCloudState={version:2,profile:{name:"Attila",goal:"Általános fittség",weeklyHours:7,strengthRatio:25},accent:"teal",checkins:{},feedback:{},plans:[]};
let syncResponseMode="non-json";
let adminUsers=[
  {id:"test-user",email:"attilla@example.com",name:"Attila",role:"admin",accessStatus:"active"},
  {id:"member-user",email:"sportolo@example.com",name:"Teszt Sportoló",role:"member",accessStatus:"active"},
];
let adminAudit=[
  {id:"audit-1",action:"invite_created",createdAt:"2026-09-24T10:30:00+00:00",actor:"attilla@example.com",target:null},
];
let downloadedExport="";
globalThis.URL.createObjectURL=()=>"blob:hybrid-export";
globalThis.URL.revokeObjectURL=()=>{};
dom.window.HTMLAnchorElement.prototype.click=function(){downloadedExport=this.download;};
globalThis.fetch = async (input,options={}) => {
  const url=String(input);
  if(url.endsWith("/api/auth")){
    return {ok:true,status:200,json:async()=>({user:{id:"test-user",email:"attilla@example.com",name:"Attila",role:"admin"}}),text:async()=>""};
  }
  if(url.endsWith("/api/admin")){
    const payload=options.body?JSON.parse(options.body):{};
    const action=payload.action||"";
    if(action==="set_user_access"){
      adminUsers=adminUsers.map(item=>item.id===payload.id?{...item,accessStatus:payload.status}:item);
      adminAudit=[{id:`audit-${adminAudit.length+1}`,action:payload.status==="suspended"?"user_suspended":"user_reactivated",createdAt:"2026-09-25T08:15:00+00:00",actor:"attilla@example.com",target:"sportolo@example.com"},...adminAudit];
    }
    if(action==="create_invite")adminAudit=[{id:`audit-${adminAudit.length+1}`,action:"invite_created",createdAt:"2026-09-25T08:10:00+00:00",actor:"attilla@example.com",target:null},...adminAudit];
    const body=action==="create_invite"
      ? {id:"invite-1",status:"active",expiresAt:"2026-09-30T12:00:00+00:00",path:"/?invite=teszt-token"}
      : action ? {ok:true} : {users:adminUsers,invites:[],audit:adminAudit};
    return {ok:true,status:action==="create_invite"?201:200,json:async()=>body,text:async()=>JSON.stringify(body)};
  }
  if(url.endsWith("/api/state?export=1"))return {ok:true,status:200,json:async()=>({}),blob:async()=>new dom.window.Blob(["{}"],{type:"application/json"}),headers:{get:name=>name.toLowerCase()==="content-disposition"?'attachment; filename="hybrid-athlete-adatexport-2026-09-25.json"':null},text:async()=>"{}"};
  if(url.endsWith("/api/model"))return {ok:true,status:200,json:async()=>({active:{id:7,trained_at:"2026-09-22T03:15:00+00:00",data_start:"2025-09-01",data_end:"2026-09-21",samples:340,model_mae:0.42,baseline_mae:0.61,eligible:true,active:true,promotion_reason:"A jelölt MAE-je jobb.",validation:{improvementPct:31.1,windowsWon:3,windowCount:3}},latest:null,readiness:{availableSamples:340,requiredSamples:132,progressPct:100,observedDays:365,dataStart:"2025-09-01",dataEnd:"2026-09-22",readyForValidation:true,coverage:[{key:"sleep_score",label:"Alváspontszám",availableDays:350,coveragePct:96},{key:"hrv",label:"Éjszakai HRV",availableDays:340,coveragePct:93},{key:"resting_hr",label:"Nyugalmi pulzus",availableDays:355,coveragePct:97},{key:"hybrid_load",label:"Edzésterhelés",availableDays:365,coveragePct:100},{key:"session_rpe",label:"Saját edzésérzet (RPE)",availableDays:40,coveragePct:11}]},schedule:{nextCheckAt:"2026-09-23T03:15:00+00:00",frequency:"daily"},lastRun:{checkedAt:"2026-09-22T03:15:00+00:00",status:"candidate_ready",due:true,reasons:["30 új adatnap érkezett"],dataEnd:"2026-09-22",message:"A validált jelölt aktiválva."}}),text:async()=>""};
  if(url.endsWith("/api/garmin"))return {ok:true,status:200,json:async()=>({status:"connected",email_hint:"at••••@example.com"}),text:async()=>""};
  if(url.endsWith("/api/sync")){
    if(syncResponseMode==="failed"){
      const body={run_id:"resume-test",status:"failed",phase:"failed",progress:42,message:"A Garmin átmenetileg nem elérhető."};
      return {ok:false,status:409,text:async()=>JSON.stringify(body)};
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
      if(patch.plans){
        const replaceDates=new Set(patch.replacePlanDates||[]);
        const byId=new Map(mockedCloudState.plans.filter(item=>!replaceDates.has(item.date)).map(item=>[item.id,item]));
        patch.plans.forEach(item=>byId.set(item.id,item));
        mockedCloudState.plans=[...byId.values()];
      }
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
  const root = createRoot(document.getElementById("root"));
  await act(async () => root.render(React.createElement(App)));
  await act(async () => new Promise(resolve => setTimeout(resolve, 25)));
  const bundledLogo=document.querySelector('.brand-logo img');
  if (!bundledLogo?.getAttribute("src")||bundledLogo.getAttribute("src")==="[object Object]") throw new Error("A bundle-ölt Hybrid Athlete logó hiányzik.");
  if (!document.querySelector(".sidebar .lucide-target")) throw new Error("A Felkészültség menüpont egyedi célikonja hiányzik.");
  if (!document.querySelector(".content")?.textContent.includes("FEJLŐDÉSTÖRTÉNET")) throw new Error("Az Áttekintés nem a kezdőképernyő.");
  if (!document.querySelector(".content")?.textContent.toLowerCase().includes("terhelési pont")) throw new Error("Az Áttekintés grafikon Y tengelyének neve vagy mértékegysége hiányzik.");
  if (!document.querySelector(".content")?.textContent.includes("X tengely: dátum")) throw new Error("Az Áttekintés grafikon X tengelyének magyarázata hiányzik.");
  const kpiDetails=[...document.querySelectorAll('.overview-kpi-details')];
  if(kpiDetails.length!==4||kpiDetails.some(item=>item.open||!item.textContent.includes('Mit jelent ez?'))) throw new Error("Az Áttekintés KPI-magyarázatai nem tömör, kibontható formában jelennek meg.");
  const chartDetails=document.querySelector('.overview-chart-details');
  if(chartDetails?.open||!chartDetails?.textContent.includes('Hybrid edzettség (CTL)')) throw new Error("A fejlődéstörténet közérthető, kibontható magyarázata hiányzik.");
  const quality=document.querySelector(".overview-quality");
  if (!quality?.textContent.includes("4 / 5 elérhető")||!quality.textContent.includes("100% Garmin-adat")||!quality.textContent.includes("461 edzés")) throw new Error("Az Áttekintés adatminőségi és lefedettségi magyarázata hiányos.");
  console.log("OK közérthető adatminőség és forráslefedettség");
  await act(async () => [...document.querySelectorAll("button")].find(node=>node.textContent.trim()==="Ma").click());
  if (!document.querySelector(".checkin-gate")) throw new Error("A Ma oldal nem az állapotfelméréssel kezdődik.");
  if (!document.querySelector(".content header")?.textContent.includes("szeptember")) throw new Error("A napi állapotfelmérés dátuma nem magyar, közérthető formátumban jelenik meg.");
  const scaleRows=[...document.querySelectorAll(".checkin-gate .scale-row")];
  if (scaleRows.length!==4||!scaleRows[0].textContent.includes("1 · nincs")||!scaleRows[1].textContent.includes("5 · kimerült vagyok")||!scaleRows[2].textContent.includes("1 · nincs kedvem")||!scaleRows[3].textContent.includes("5 · nagyon feszült vagyok")) throw new Error("Az állapotfelmérés 1–5 skáláinak közérthető végpontjai hiányoznak.");
  for (const row of scaleRows) {
    const first=row.querySelector("button");
    if(first.getAttribute("aria-pressed")!=="false"||!first.getAttribute("aria-label")?.includes("1 az 5-ből")) throw new Error("Az állapotfelmérés választógombjai nem hozzáférhetők.");
    await act(async()=>first.click());
    if(first.getAttribute("aria-pressed")!=="true") throw new Error("Az állapotfelmérés kiválasztott értéke nincs jelezve a segítő technológiáknak.");
  }
  const illness = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Betegségérzetem van");
  if(illness.getAttribute("aria-pressed")!=="false"||!document.querySelector(".check-alert-help")?.textContent.includes("pihenőnapra")) throw new Error("A fájdalom- és betegségjelzés következménye vagy állapota nincs elmagyarázva.");
  await act(async () => illness.click());
  if(illness.getAttribute("aria-pressed")!=="true") throw new Error("A betegségjelzés aktív állapota nem hozzáférhető.");
  const saveCheckin = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Mentés és a javaslat kiszámítása");
  await act(async () => saveCheckin.click());
  if (!document.querySelector(".decision-copy")?.textContent.includes("Teljes pihenő")) throw new Error("A betegségérzet nem írta felül biztonságosan az ajánlást.");
  if (!cloudPatches.some(patch=>patch.checkin?.date===budapestToday())) throw new Error("A napi check-in nem a mai napra indított Neon-mentést.");
  console.log("OK közérthető és hozzáférhető napi check-in, biztonsági felülírással");
  await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
  const explainedKpi=document.querySelector('.week-stats>div.explained-value');
  if (explainedKpi?.dataset.metric!=="Terhelés" || !explainedKpi.dataset.explanation?.includes("forrását mindig külön jelöljük")) throw new Error("A terhelés forrását tisztázó laikus magyarázat nem épült fel.");
  if (explainedKpi.getAttribute("tabindex")!=="0") throw new Error("A mérőszám-magyarázat nem érhető el billentyűzettel.");
  console.log("OK desktop logó és laikus mérőszám-magyarázat");
  await act(async () => new Promise(resolve=>setTimeout(resolve,25)));
  const readinessMetric=document.querySelector('.metric-wrap .metric');
  if (!readinessMetric) throw new Error("A readiness mérőszámsor nem jelent meg.");
  if (readinessMetric.classList.contains("explained-value")) throw new Error("A lenyitható readiness soron felesleges hover tooltip maradt.");
  await act(async () => readinessMetric.click());
  if (!document.querySelector('.metric-detail')?.textContent.includes("MIT JELENT MOST?")) throw new Error("A readiness részletes értelmezése nem nyitható meg.");
  if (!document.querySelector('.metric-detail')?.textContent.includes("ADATMINŐSÉG")) throw new Error("A readiness adatminőségi magyarázata hiányzik.");
  console.log("OK readiness részletek és adatminőség");
  const overview = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Áttekintés");
  await act(async () => overview.click());
  const sync = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "SZINKRONIZÁLÁS");
  await act(async () => sync.click());
  if (!document.querySelector(".overview-sync-position")?.textContent.includes("érvénytelen választ")) throw new Error("A nem JSON szinkronhiba nem kapott érthető üzenetet az Áttekintés oldalon.");
  console.log("OK online szinkronhiba kezelése");
  syncResponseMode="failed";
  await act(async () => sync.click());
  if (![...document.querySelectorAll("button")].some(node=>node.textContent.trim()==="SZINKRON FOLYTATÁSA")) throw new Error("A megszakadt szinkron nem folytatható ugyanabból a futásból.");
  console.log("OK megszakadt szinkron folytatása");
  for (const label of ["Naptár", "Trendek", "Cél", "Elemzések", "Napló", "Profil", "Beállítások"]) {
    const button = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === label);
    if (!button) throw new Error(`Hiányzó navigációs gomb: ${label}`);
    await act(async () => button.click());
    const content = document.querySelector(".content")?.textContent || "";
    if (!content.includes(label === "Elemzések" ? "Mi működik nálam" : label === "Cél" ? "Felkészültség" : label === "Napló" ? "Edzések" : label === "Naptár" ? "Terv és tény" : label === "Trendek" ? "Terhelés és forma" : label)) {
      throw new Error(`A(z) ${label} oldal nem renderelődött.`);
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
      const translation=document.querySelector('.decision-translation');
      if(!translation?.textContent.includes('Mi változott?')||!translation.textContent.includes('Mi állhat mögötte?')||!translation.textContent.includes('Mit tehetsz?')||!translation.textContent.includes('előző 90 napból')) throw new Error("A Trendek döntéstámogató időszak-összehasonlítása hiányzik.");
      const sixtyDays=[...document.querySelectorAll('.segmented button')].find(node=>node.textContent.trim()==='60 nap');
      await act(async()=>sixtyDays.click());
      if(!document.querySelector('.decision-translation')?.textContent.includes('előző 60 napból')) throw new Error("A 60 napos időszak összehasonlítása nem frissült.");
      if (!document.querySelector('.chart-card .metric-header-explanation')?.dataset.explanation?.includes("hosszú távú edzettség")) throw new Error("A CTL/ATL/TSB grafikon laikus magyarázata hiányzik.");
      const range = [...document.querySelectorAll(".segmented button")].find(node => node.textContent.trim() === "30 nap");
      await act(async () => range.click());
      if (!range.classList.contains("active")) throw new Error("A trendek időszakváltása nem működik.");
      if (document.querySelectorAll(".trend-summary .card").length !== 5) throw new Error("Hiányoznak a fejlődéstörténet összesítői.");
      console.log("OK fejlődéstörténet és időszakváltás");
    }
    if (label === "Elemzések") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      const weeklyTranslation=document.querySelector('.decision-translation');
      if(!weeklyTranslation?.textContent.includes('A heti adatok jelentése röviden')||!weeklyTranslation.textContent.includes('Mi változott?')||!weeklyTranslation.textContent.includes('előző 7 napból')) throw new Error("Az Elemzések heti, közérthető értelmezése hiányzik.");
      const modelStatus=document.querySelector('.model-status');
      if (!modelStatus?.textContent.includes("Aktív személyes regenerációs modell")) throw new Error("Az automatikus személyes modell állapota nem jelent meg.");
      if (!modelStatus.textContent.includes("átlagos abszolút hiba 0,42")||!modelStatus.textContent.includes("nem terhelhetőségi pontszám")) throw new Error("A modell pontosságának laikus magyarázata hiányzik.");
      if (!modelStatus.textContent.includes("340 / 132 nap")||!modelStatus.textContent.includes("31,1% kisebb hiba")||!modelStatus.textContent.includes("3 / 3 jobb")) throw new Error("A modell adatalkalmassági vagy validációs összefoglalója hiányzik.");
      if (!modelStatus.textContent.includes("Éjszakai HRV")||!modelStatus.textContent.includes("Következő automatikus ellenőrzés")) throw new Error("A modell adatlefedettsége vagy ütemezése hiányzik.");
      console.log("OK ütemezett személyes modellállapot, adatalkalmasság és közérthető pontosság");
    }
    if (label === "Beállítások") {
      await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));
      const settingsNav=document.querySelector('.settings-section-nav');
      const settingsTargets=settingsNav?[...settingsNav.querySelectorAll('a')].map(link=>link.getAttribute('href')):[];
      if(!settingsNav||!settingsTargets.includes('#settings-data')||!settingsTargets.includes('#settings-personalization')||!settingsTargets.includes('#settings-account')||!settingsTargets.every(target=>document.querySelector(target))) throw new Error("A Beállítások szakasznavigációja hiányos.");
      const dataManagement=document.querySelector(".data-management-card");
      if (!dataManagement?.textContent.includes("Milyen adatok vannak a fiókodban?")) throw new Error("Az adatkezelési áttekintő hiányzik a Beállításokból.");
      if (!dataManagement.textContent.includes("461 edzés")||!dataManagement.textContent.includes("Profil, tervek, check-inek és edzésérzet")) throw new Error("Az adatkezelési áttekintő nem mutatja közérthetően a tárolt adatkategóriákat.");
      if (!dataManagement.textContent.includes("Garmin leválasztása nem")||!dataManagement.textContent.includes("Titkosított munkamenettoken")) throw new Error("A Garmin-kapcsolat és a megőrzött adatok magyarázata hiányzik.");
      const retentionNote=document.querySelector(".connection-retention-note");
      if (!retentionNote?.textContent.includes("szinkronizált előzmények")||!retentionNote.textContent.includes("megmaradnak")) throw new Error("A Garmin leválasztás következménye nincs elmagyarázva.");
      const access=document.querySelector(".admin-access-card");
      if (!access?.textContent.includes("Zárt hozzáférés")) throw new Error("Az adminisztrátori hozzáférés-kezelés hiányzik.");
      const dataExport=document.querySelector(".data-export-card");
      if (!dataExport?.textContent.includes("Saját adatok letöltése")||!dataExport.textContent.includes("titkos Garmin-tokent")) throw new Error("A biztonságos sajátadatexport hiányzik a Beállításokból.");
      await act(async()=>[...dataExport.querySelectorAll("button")].find(node=>node.textContent.includes("Saját adatok letöltése")).click());
      if(downloadedExport!=="hybrid-athlete-adatexport-2026-09-25.json"||!dataExport.textContent.includes("letöltődött")) throw new Error("A sajátadatexport letöltési folyamata nem működik.");
      if (!access.textContent.includes("Adminisztrátori napló")||!access.textContent.includes("Meghívólink létrehozva")) throw new Error("Az adminisztrátori biztonsági napló hiányzik.");
      if (access.textContent.includes("teszt-token")) throw new Error("A titkos meghívótoken megjelent az adminisztrátori naplóban.");
      const invite=[...access.querySelectorAll("button")].find(node=>node.textContent.includes("Új meghívólink"));
      await act(async()=>invite.click());
      await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));
      if (!access.querySelector('.admin-generated-link input')?.value.includes("?invite=teszt-token")) throw new Error("A meghívólink nem generálódott le.");
      const suspend=[...access.querySelectorAll("button")].find(node=>node.textContent.trim()==="Felfüggesztés");
      await act(async()=>suspend.click());
      const confirmSuspend=[...access.querySelectorAll("button")].find(node=>node.textContent.trim()==="Biztosan felfüggesztem");
      if (!confirmSuspend) throw new Error("A hozzáférés felfüggesztése nem kér megerősítést.");
      await act(async()=>confirmSuspend.click());
      await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));
      if (!access.textContent.includes("FELFÜGGESZTVE")||![...access.querySelectorAll("button")].some(node=>node.textContent.trim()==="Újraaktiválás")) throw new Error("A felhasználói hozzáférés nem függeszthető fel és nem aktiválható újra.");
      if (!access.textContent.includes("Felhasználó felfüggesztve")||!access.textContent.includes("sportolo@example.com")) throw new Error("A felfüggesztés nem került az adminisztrátori naplóba.");
      console.log("OK zárt adminisztrátori meghívás, hozzáférés-kezelés és biztonsági napló");
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
      const saveAdaptive=[...adaptiveModal.querySelectorAll("button")].find(node=>node.textContent.trim()==="Adaptált hét mentése");
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
    if (label === "Napló") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      if(!document.querySelector('.planning-flow')?.querySelector('[aria-current="step"]')?.textContent.includes('Visszajelzés')) throw new Error("A tervezési folyamat nem jelöli a Napló lépést.");
      const weeklyClosure=document.querySelector('.weekly-closure');
      if(!weeklyClosure?.textContent.includes('Mi teljesült?')||!weeklyClosure.textContent.includes('Mit jelez?')||!weeklyClosure.textContent.includes('Következő döntés')) throw new Error("A Napló heti lezárása vagy döntési magyarázata hiányzik.");
      if(!weeklyClosure.textContent.includes('1 edzés')||!weeklyClosure.textContent.includes('0 / 1')) throw new Error("A heti lezárás nem a külön Garmin-aktivitásokat és visszajelzéseket összesíti.");
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
      console.log("OK adatkezelési áttekintő, profilkép- és avatarbeállítás");
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
  dashboardFixture.today = "2020-01-01";
  const todayButton = [...document.querySelectorAll(".sidebar button")].find(node => node.textContent.trim() === "Ma");
  await act(async () => todayButton.click());
  if (!document.querySelector(".content")?.textContent.includes("Nincs mai Garmin-összesítés")) throw new Error("Régi Garmin-adatokból mai ajánlás jelent meg.");
  if (document.querySelector(".decision")) throw new Error("Elavult adatok mellett látható az ajánlás.");
  dashboardFixture.today = budapestToday();
  const retry = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Adatok újratöltése");
  await act(async () => retry.click());
  if (document.querySelector(".content")?.textContent.includes("Nincs mai Garmin-összesítés")) throw new Error("A friss adatok újratöltése nem oldotta fel az adatkaput.");
  console.log("OK elavult napi adatok kizárása és újratöltés");
  await act(async () => [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Beállítások").click());
  const passwordCard=document.querySelector(".password-change-card");
  if(!passwordCard?.textContent.includes("minden aktív eszközről kijelentkeztetünk")) throw new Error("A jelszóváltoztatás biztonsági következménye nincs elmagyarázva.");
  const passwordInputs=passwordCard.querySelectorAll('input[type="password"]');
  if(passwordInputs.length!==3||passwordInputs[0].autocomplete!=="current-password"||![...passwordInputs].slice(1).every(input=>input.autocomplete==="new-password"&&input.minLength===10)) throw new Error("A jelszóváltoztatási űrlap mezői vagy böngészőbiztonsági jelölései hiányosak.");
  if(![...passwordCard.querySelectorAll("button")].some(button=>button.textContent.trim()==="Jelszó módosítása")) throw new Error("A jelszóváltoztatás műveleti gombja hiányzik.");
  console.log("OK önkiszolgáló jelszóváltoztatási felület");
  const deletionCard=document.querySelector(".account-deletion-card");
  if(!deletionCard?.textContent.includes("Fiók és személyes adatok törlése")||!deletionCard.textContent.includes("Garmin-kapcsolatodat")) throw new Error("A fiók- és adattörlés hatása nincs közérthetően elmagyarázva.");
  const prepareDeletion=[...deletionCard.querySelectorAll("button")].find(button=>button.textContent.includes("Fiók törlésének előkészítése"));
  if(!prepareDeletion||prepareDeletion.getAttribute("aria-expanded")!=="false") throw new Error("A fióktörlés biztonságos, zárt kezdőállapota hiányzik.");
  await act(async()=>prepareDeletion.click());
  if(!deletionCard.textContent.includes("nem vonható vissza")||!deletionCard.textContent.includes("név és e-mail nélküli anonim azonosító")) throw new Error("A visszafordíthatatlan törlés és a naplómegőrzés magyarázata hiányzik.");
  const deletePassword=deletionCard.querySelector('input[type="password"]');
  const deletePhrase=deletionCard.querySelector('input[type="text"]');
  const finalDelete=[...deletionCard.querySelectorAll("button")].find(button=>button.textContent.includes("Fiók végleges törlése"));
  if(deletePassword?.autocomplete!=="current-password"||deletePhrase?.autocomplete!=="off"||!deletionCard.textContent.includes("FIÓK TÖRLÉSE")||!finalDelete?.disabled) throw new Error("A fióktörlés jelszavas, pontos megerősítése hiányos.");
  console.log("OK biztonságos fiók- és személyesadattörlési felület");
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
