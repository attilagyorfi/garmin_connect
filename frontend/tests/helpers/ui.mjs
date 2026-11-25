// jsdom + Vite SSR harness for component tests: no browser, no real server, every request goes to the given fetch mock.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";
import { createServer } from "vite";

const dom = new JSDOM('<!doctype html><html lang="hu"><head><title>Hybrid Athlete</title></head><body></body></html>', { url: "http://localhost/" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
globalThis.localStorage = dom.window.localStorage;
globalThis.sessionStorage = dom.window.sessionStorage;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.SVGElement = dom.window.SVGElement;
globalThis.Event = dom.window.Event; // useGarminSync dispatches with the global constructor
globalThis.MutationObserver = dom.window.MutationObserver;
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
console.warn = () => {}; // Recharts warns about the missing layout in jsdom

// React DOM must load after the DOM globals exist (see scripts/test-navigation.mjs).
const { default: React, act } = await import("react");
const { createRoot } = await import("react-dom/client");
const { default: axe } = await import("axe-core");
// Test files run in parallel processes: a shared Vite cache folder makes them fail on each other's rename.
const cacheDir = mkdtempSync(join(tmpdir(), "hybrid-vite-"));
const vite = await createServer({ cacheDir, root: fileURLToPath(new URL("../..", import.meta.url)), logLevel: "error", server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom", optimizeDeps: { noDiscovery: true } });

export { React, act };
export const load = path => vite.ssrLoadModule(path);
export const close = async () => { await vite.close(); rmSync(cacheDir, { recursive: true, force: true }); dom.window.close(); };

export const ok = body => ({ ok: true, status: 200, headers: { get: () => null }, json: async () => body, text: async () => JSON.stringify(body) });
export const fail = (status, body = {}) => ({ ok: false, status, headers: { get: () => null }, json: async () => body, text: async () => JSON.stringify(body) });
export const noData = () => fail(404, { error: "Még nincs szinkronizált Garmin-adat.", code: "no_dashboard_data" });
export const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
// handlers: { "/api/dashboard": (options, url) => response | promise }
export const mockFetch = handlers => { globalThis.fetch = async (input, options = {}) => { const url = String(input), handler = handlers[url]; if (!handler) throw new Error(`Váratlan kérés: ${url}`); return handler(options, url); }; };

export const settle = (ms = 20) => act(async () => new Promise(resolve => setTimeout(resolve, ms)));
export async function mount(element) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host);
  const render = next => act(async () => root.render(next));
  await render(element); await settle();
  return { host, render, unmount: async () => { await act(async () => root.unmount()); host.remove(); } };
}
export const button = (host, text) => [...host.querySelectorAll("button")].find(node => node.textContent.trim() === text);
export const click = async node => { if (!node) throw new Error("Nincs ilyen gomb."); await act(async () => node.click()); await settle(); };
const PROTOTYPES = { TEXTAREA: "HTMLTextAreaElement", SELECT: "HTMLSelectElement", INPUT: "HTMLInputElement" };
export const type = (node, value) => act(async () => { Object.getOwnPropertyDescriptor(window[PROTOTYPES[node.tagName]].prototype, "value").set.call(node, value); node.dispatchEvent(new window.Event(node.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
export const submit = async form => { await act(async () => form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }))); await settle(); };
export const refresh = async () => { await act(async () => window.dispatchEvent(new window.Event("hybrid-dashboard-refresh"))); await settle(); };
export const alerts = host => [...host.querySelectorAll('[role="alert"]')].map(node => node.textContent);
export const statuses = host => [...host.querySelectorAll('[role="status"]')].map(node => node.textContent);
export async function assertAccessible(context) {
  const { violations } = await axe.run(context, { rules: { "color-contrast": { enabled: false }, "link-in-text-block": { enabled: false } }, resultTypes: ["violations"] });
  const blocking = violations.filter(item => item.impact === "critical" || item.impact === "serious");
  if (blocking.length) throw new Error(`Akadálymentességi hiba: ${blocking.map(item => `${item.id}: ${item.nodes.map(node => node.target.join(" ")).join(", ")}`).join("; ")}`);
}

export const budapestDay = (offset = 0) => new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Budapest", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(Date.now() + offset * 86400000));
export const testProfile = { name: "Teszt Sportoló", experience: "középhaladó", goal: "Hibrid teljesítmény", eventName: "", eventDate: "", eventType: "", weeklyHours: 8, strengthRatio: 30, trainingDays: ["H", "K", "Sze", "Cs", "P", "Szo"], restDay: "V", limitations: "", preference: "kiegyensúlyozott", avatarPreset: "athlete", avatarImage: "" };
export const session = (id = "run-1", date = budapestDay(), name = "Teszt futás") => ({ id, date, type: "Futás", name, durationMin: 48, avgHr: 137, distanceKm: 8.2, load: 64 });
export const dashboard = (sessions = [session()], extra = {}) => ({ source: "garmin", today: budapestDay(), readiness: 78, confidence: "magas", dataQuality: {}, decision: { title: "Zone 2 alapozás", duration: "45–70 perc", intensity: "közepes", rationale: "Teszt." }, week: { total_load: 420, change_pct: 4, recommendations: ["Tartsd a kiegyensúlyozott struktúrát."] }, sessions, heat: [], metrics: [], trends: [], zones: [0, 48, 0, 0, 0], coaching: { tips: [], weekly: null }, benchmarks: { profile: { sex: "male", age: 35 }, demo: false, sources: [], cards: [{ key: "steps", title: "Napi lépésszám", status: "missing", headline: "Nincs napi lépésszám adat.", valueText: "—", percentile: null, level: null, category: null, confidence: null, sources: [] }] }, ...extra });
