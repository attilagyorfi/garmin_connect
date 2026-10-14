import { useEffect } from "react";

// Every pop-up in the app is a `.modal-backdrop > .modal` rendered by its own component. Instead of repeating the
// same dialog plumbing in each of them, one observer gives all of them the same keyboard and screen-reader behaviour:
// dialog role + name (from the heading), focus moved in on open and back on close, Tab kept inside, Esc closes.

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]:not([tabindex="-1"])';
let counter = 0;

const focusables = modal => [...modal.querySelectorAll(FOCUSABLE)].filter(node => node.offsetParent !== null || node === document.activeElement);

export function prepareModal(modal) {
  if (modal.dataset.a11yReady) return;
  modal.dataset.a11yReady = "1";
  if (!modal.getAttribute("role")) modal.setAttribute("role", "dialog");
  if (!modal.getAttribute("aria-modal")) modal.setAttribute("aria-modal", "true");
  if (!modal.getAttribute("aria-label") && !modal.getAttribute("aria-labelledby")) {
    const heading = modal.querySelector("h1,h2,h3");
    if (heading) {
      heading.id ||= `modal-title-${++counter}`;
      modal.setAttribute("aria-labelledby", heading.id);
    }
  }
  if (!modal.hasAttribute("tabindex")) modal.setAttribute("tabindex", "-1");
  if (!modal.contains(document.activeElement)) {
    // the close button is usually first; start on the first real control after it when there is one
    const items = focusables(modal), first = items.find(node => !node.classList.contains("close")) || items[0] || modal;
    first.focus({ preventScroll: true });
  }
}

function topModal() {
  const all = document.querySelectorAll(".modal");
  return all[all.length - 1] || null;
}

function closeModal(modal) {
  const close = modal.querySelector(".close") || [...modal.querySelectorAll("button")].find(node => /^(Mégse|Bezárás)$/.test(node.textContent.trim()));
  if (close) close.click();
  else modal.closest(".modal-backdrop")?.click();
}

/** Installs the shared dialog behaviour for every `.modal` (call once, near the app root). */
export function useModalAccessibility() {
  useEffect(() => {
    let returnTo = null, wasOpen = false;
    const sync = () => {
      const modal = topModal();
      if (modal && !wasOpen) returnTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (modal) prepareModal(modal);
      if (!modal && wasOpen && returnTo?.isConnected) returnTo.focus({ preventScroll: true });
      wasOpen = Boolean(modal);
    };
    const onKey = event => {
      const modal = topModal();
      if (!modal) return;
      if (event.key === "Escape") { event.preventDefault(); closeModal(modal); return; }
      if (event.key !== "Tab") return;
      const items = focusables(modal);
      if (!items.length) { event.preventDefault(); modal.focus(); return; }
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || !modal.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !modal.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("keydown", onKey);
    sync();
    return () => { observer.disconnect(); document.removeEventListener("keydown", onKey); };
  }, []);
}
