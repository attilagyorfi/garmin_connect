import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { availableSteps, tourAnchor } from "../lib/tourSteps.js";

const GAP = 14, WIDTH = 360;

function placement(rect) {
  if (!rect) return { style: { left: "50%", top: "50%", transform: "translate(-50%, -50%)" }, side: "center" };
  const vw = window.innerWidth, vh = window.innerHeight;
  // Sidebar anchors sit at the left edge, so the card goes to their right; otherwise below or above.
  if (rect.right + GAP + WIDTH < vw) return { style: { left: rect.right + GAP, top: Math.max(16, Math.min(rect.top - 8, vh - 280)) }, side: "right" };
  if (rect.bottom + GAP + 220 < vh) return { style: { left: Math.max(16, Math.min(rect.left, vw - WIDTH - 16)), top: rect.bottom + GAP }, side: "bottom" };
  return { style: { left: Math.max(16, Math.min(rect.left, vw - WIDTH - 16)), top: Math.max(16, rect.top - GAP - 220) }, side: "top" };
}

// A guided tour: a dimmed page with the current element cut out, and a small dialog next to it. The dialog uses the
// shared `.modal` behaviour (role, focus, Tab trap, Esc = skip) from lib/modalA11y.js.
export function GuidedTour({ onFinish }) {
  const steps = useMemo(() => availableSteps(), []);
  const [index, setIndex] = useState(0), [rect, setRect] = useState(null);
  const step = steps[index], last = index === steps.length - 1;

  useLayoutEffect(() => {
    const measure = () => {
      const anchor = tourAnchor(step?.target);
      if (!anchor) { setRect(null); return; }
      anchor.scrollIntoView?.({ block: "nearest" });
      const box = anchor.getBoundingClientRect();
      setRect({ top: box.top, left: box.left, width: box.width, height: box.height, right: box.right, bottom: box.bottom });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [step]);

  useEffect(() => {
    const onKey = event => {
      if (event.key === "ArrowRight" && !last) setIndex(value => value + 1);
      if (event.key === "ArrowLeft" && index > 0) setIndex(value => value - 1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [index, last]);

  // Focus moves with the step, so screen readers announce the new title.
  useEffect(() => { document.getElementById("tour-title")?.focus({ preventScroll: true }); }, [index]);

  if (!step) return null;
  const { style, side } = placement(rect);
  const pad = 6;
  return <div className="tour-layer">
    {rect ? <div className="tour-spotlight" aria-hidden="true" style={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }}/> : <div className="tour-dim" aria-hidden="true"/>}
    <div className={`modal tour-popover tour-${side}`} role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-text" style={style}>
      <button className="close" aria-label="Bemutató bezárása" onClick={() => onFinish("skipped")}><X size={16}/></button>
      <span className="eyebrow">BEMUTATÓ · {index + 1} / {steps.length}</span>
      <h2 id="tour-title" tabIndex={-1}>{step.title}</h2>
      <p id="tour-text">{step.text}</p>
      <div className="tour-progress" aria-hidden="true">{steps.map((_, dot) => <i key={dot} className={dot === index ? "active" : dot < index ? "seen" : ""}/>)}</div>
      <div className="tour-actions">
        {!last && <button className="tour-skip" onClick={() => onFinish("skipped")}>Kihagyás</button>}
        <span/>
        {index > 0 && <button onClick={() => setIndex(index - 1)}>Vissza</button>}
        <button className="primary" onClick={() => last ? onFinish("done") : setIndex(index + 1)}>{last ? "Befejezés" : "Tovább"}</button>
      </div>
    </div>
  </div>;
}
