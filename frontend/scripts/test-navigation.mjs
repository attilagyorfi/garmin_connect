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
dom.window.HTMLElement.prototype.attachEvent = () => {};
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
const dashboardFixture={
  today:"2026-08-19",readiness:78,confidence:"magas",decision:{title:"Zone 2 alapozás",duration:"45–70 perc",intensity:"közepes",rationale:"Teszt regenerációs indoklás."},week:{total_load:420,change_pct:4,recommendations:["Tartsd a kiegyensúlyozott struktúrát."]},
  sessions:[{id:"test-activity",date:"2026-08-18",type:"Futás",name:"Teszt Zone 2 futás",durationMin:48,avgHr:137,distanceKm:8.2,load:64}],heat:[],metrics:[],trends:[],zones:[0,48,0,0,0]
};
const cloudPatches=[];
let mockedCloudState={version:2,profile:null,accent:"teal",checkins:{},feedback:{},plans:[]};
globalThis.fetch = async (input,options={}) => {
  const url=String(input);
  if(url.endsWith("/api/sync"))return {ok:false,status:404,text:async()=>"The page could not be found"};
  if(url.endsWith("/api/state")){
    if(options.method==="PATCH"){
      const patch=JSON.parse(options.body);cloudPatches.push(patch);
      if(patch.profile)mockedCloudState.profile=patch.profile;
      if(patch.accent)mockedCloudState.accent=patch.accent;
      if(patch.checkin)mockedCloudState.checkins[patch.checkin.date]=patch.checkin.value;
      if(patch.feedback)mockedCloudState.feedback[patch.feedback.activityId]=patch.feedback.value;
      if(patch.plan)mockedCloudState.plans=[...mockedCloudState.plans.filter(item=>item.id!==patch.plan.id),patch.plan];
      if(patch.plans)mockedCloudState.plans=[...mockedCloudState.plans,...patch.plans];
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
  const bundledLogo=document.querySelector('.brand-logo img');
  if (!bundledLogo?.getAttribute("src")||bundledLogo.getAttribute("src")==="[object Object]") throw new Error("A bundle-ölt Hybrid Athlete logó hiányzik.");
  await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
  const explainedKpi=document.querySelector('.week-stats>div.explained-value');
  if (!explainedKpi?.dataset.explanation?.includes("regenerációs igényt")) throw new Error("A laikus mérőszám-magyarázat nem épült fel.");
  if (explainedKpi.getAttribute("tabindex")!=="0") throw new Error("A mérőszám-magyarázat nem érhető el billentyűzettel.");
  console.log("OK desktop logó és laikus mérőszám-magyarázat");
  await act(async () => new Promise(resolve=>setTimeout(resolve,25)));
  const readinessMetric=document.querySelector('.metric-wrap .metric');
  if (!readinessMetric) throw new Error("A readiness mérőszámsor nem jelent meg.");
  await act(async () => readinessMetric.click());
  if (!document.querySelector('.metric-detail')?.textContent.includes("MIT JELENT MOST?")) throw new Error("A readiness részletes értelmezése nem nyitható meg.");
  if (!document.querySelector('.metric-detail')?.textContent.includes("ADATMINŐSÉG")) throw new Error("A readiness adatminőségi magyarázata hiányzik.");
  console.log("OK readiness részletek és adatminőség");
  const sync = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "SZINKRON");
  await act(async () => sync.click());
  if (!document.querySelector(".header-actions")?.textContent.includes("Az online Garmin-szinkron még nincs bekötve")) throw new Error("A nem JSON szinkronhiba nem kapott érthető üzenetet.");
  console.log("OK online szinkronhiba kezelése");
  const illness = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Betegségérzetem van");
  if (!illness) throw new Error("Hiányzik a betegségérzet check-in vezérlője.");
  await act(async () => illness.click());
  const saveCheckin = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "Mentés és újraszámolás");
  await act(async () => saveCheckin.click());
  if (!document.querySelector(".decision-copy")?.textContent.includes("Teljes pihenő")) throw new Error("A betegségérzet nem írta felül biztonságosan az ajánlást.");
  if (![...Array(localStorage.length).keys()].map(index=>localStorage.key(index)).some(key=>key?.startsWith("hybrid-checkin-"))) throw new Error("A napi check-in nem mentődött el.");
  if (!cloudPatches.some(patch=>patch.checkin?.date==="2026-08-19")) throw new Error("A napi check-in nem indított Neon-mentést.");
  console.log("OK napi check-in és biztonsági felülírás");
  for (const label of ["Naptár", "Trendek", "Cél", "Insights", "Napló", "Profil", "Beállítások"]) {
    const button = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === label);
    if (!button) throw new Error(`Hiányzó navigációs gomb: ${label}`);
    await act(async () => button.click());
    const content = document.querySelector(".content")?.textContent || "";
    if (!content.includes(label === "Insights" ? "Mi működik nálam" : label === "Cél" ? "Felkészültség" : label === "Napló" ? "Edzések" : label === "Naptár" ? "Terv és tény" : label === "Trendek" ? "Terhelés és forma" : label)) {
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
      if (document.querySelectorAll(".goal-component").length !== 5) throw new Error("A felkészültségi összetevők hiányoznak.");
      const edit = [...document.querySelectorAll("button")].find(node => node.textContent.trim() === "CÉL SZERKESZTÉSE");
      await act(async () => edit.click());
      if (!document.querySelector(".content")?.textContent.includes("Profil")) throw new Error("A Cél oldalról nem nyitható meg a Profil.");
      console.log("OK célfelkészültség és profilszerkesztés");
    }
    if (label === "Napló") {
      await act(async () => new Promise(resolve=>setTimeout(resolve,5)));
      if (document.querySelectorAll('.table-wrap th.metric-header-explanation').length<5) throw new Error("A Napló számoszlopainak magyarázata hiányzik.");
      const activity = document.querySelector(".activity-row");
      if (!activity) throw new Error("A Garmin-edzés nem jelent meg a naplóban.");
      await act(async () => activity.click());
      const modal = document.querySelector(".activity-modal");
      if (!modal?.textContent.includes("Teszt Zone 2 futás")) throw new Error("Az edzésrészlet nem nyílt meg.");
      const rpe = [...modal.querySelectorAll(".rpe-picker button")].find(node => node.textContent.trim() === "8");
      await act(async () => rpe.click());
      const save = [...modal.querySelectorAll("button")].find(node => node.textContent.trim() === "Visszajelzés mentése");
      await act(async () => save.click());
      const stored = JSON.parse(localStorage.getItem("hybrid-activity-feedback") || "{}");
      if (stored["test-activity"]?.rpe !== 8) throw new Error("Az edzés-visszajelzés nem mentődött el.");
      if (!cloudPatches.some(patch=>patch.feedback?.activityId==="test-activity"&&patch.feedback.value.rpe===8)) throw new Error("Az RPE nem indított Neon-mentést.");
      console.log("OK edzésrészlet és RPE-visszajelzés");
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
