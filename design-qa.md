# Desktop design QA

## Evidence

- Source visual truth: `C:/Users/User/.codex/state/plugins/product-design/assets/hybrid-athlete-desktop/01-ma-fresh.png`
- Implementation screenshot: `C:/Users/User/Documents/ChatGPT/Garmin/output/playwright/desktop-design-final.png`
- Combined comparison: `C:/Users/User/Documents/ChatGPT/Garmin/output/playwright/desktop-design-comparison-passed.jpg`
- Target CSS viewport: 1920 × 1180, desktop dark mode, demo-data `Ma` state.
- Source pixels: 919 × 540, an approximately 0.48-density export of the specified 1920 × 1180 design viewport.
- Implementation pixels: 1920 × 1180 at device scale factor 1.
- Normalization: the combined comparison scales both captures to the same 900 px evidence height while preserving aspect ratio. Browser presentation chrome in the source is excluded from product-level findings.

## Full-view comparison

The implementation matches the source hierarchy: narrow fixed sidebar, compact page header, large verdict card in the left column, 12-week load heatmap and weekly frame in the right rail, inline check-in, readiness details, recent sessions, and near-black/obsidian card surfaces. The implementation keeps the current product's additional navigation destinations because they are working features, not empty design placeholders.

## Focused comparison

The verdict/check-in region was compared separately because it contains the most fidelity-sensitive typography, spacing, controls, and semantic colors. The first implementation used continuous sliders and a wide default Streamlit sidebar; both produced visible density drift. The final capture uses 1–5 segmented controls, a three-column check-in grid, compact note/save row, and a measured 236 px sidebar.

## Required fidelity surfaces

- Fonts and typography: Geist/Geist Mono are requested through the app stylesheet with system fallbacks. Uppercase mono eyebrow labels, KPI numerals, tracking, weights, and heading hierarchy follow the reference. No blocking wrapping or truncation remains.
- Spacing and layout rhythm: 236 px sidebar, 14 px cards, compact 4 px-based rhythm, two-column desktop layout, 20 px major gap, and inset note tiles match the source proportions. The page has no horizontal overflow at 1920 px or 390 px.
- Colors and visual tokens: near-black `#0f0f0f`, obsidian `#1e1e1e`, teal `#14b8a6`, semantic blue/amber/red, translucent borders, and restrained shadows map to the handoff tokens.
- Image and asset fidelity: the reference contains no photography or illustration. Icons are not replaced with emoji or raster placeholders. The current wordmark uses a compact typographic H tile rather than the future production vector mark; this is non-blocking follow-up polish.
- Copy and content: Hungarian informal product copy is preserved. Live/demo analytics values remain authoritative, so the exact example numbers differ intentionally from the static reference.

## Comparison history

### Iteration 1 — blocked

- P1: Streamlit's default sidebar rendered at roughly 374 px instead of the specified 236 px, compressing the main canvas.
- P2: always-visible Garmin/demo controls dominated the navigation area.
- P2: continuous sliders made the check-in substantially taller and less scannable than the source.
- P2: the right-rail KPI row used minimum-width Streamlit metric cards and appeared crowded.

Fixes: forced and measured the sidebar at 236 px; moved data controls into a collapsed `Adatkapcsolat` section; replaced sliders with compact segmented controls in a 3-column grid; replaced the rail metrics with source-proportioned KPI tiles.

### Iteration 2 — passed

- Post-fix evidence: `desktop-design-final.png` and `desktop-design-comparison-passed.jpg`.
- Browser console: no warnings or errors captured.
- Primary interactions tested: sidebar navigation to `Naptár`, return to `Ma`, sidebar collapse behavior, desktop 1920 px layout, and 390 px responsive layout.
- Automated verification: 52 tests passed.

## Remaining P3 polish

- Replace the temporary typographic H tile with a packaged production logo asset when one is exported from the supplied mark.
- A future Streamlit component could move the sync button from the collapsed data section into the exact top-bar position without changing synchronization behavior.
- The additional working navigation destinations remain more numerous than the six-item design shell; consolidating them requires a separate information-architecture decision.

## Final result

final result: passed

## Secondary-view extension — Napló

- Source visual truth: `C:/Users/User/.codex/state/plugins/product-design/assets/hybrid-athlete-desktop/07-naplo.png`.
- Implementation screenshot: `C:/Users/User/Documents/ChatGPT/Garmin/output/playwright/desktop-naplo-final.png`.
- Combined comparison: `C:/Users/User/Documents/ChatGPT/Garmin/output/playwright/desktop-naplo-comparison.jpg`.
- Viewport: 1920 × 1180, dark mode, demo activity history.
- Compared surfaces: page hierarchy, filter/search placement, table density, date/type/title/duration/HR/RPE/load/adherence fields, sidebar state, colors, typography, spacing, and copy.
- Fixes made: compact ISO dates, integer duration/heart-rate formatting, explicit column sizing, modality filters, search, plan-adherence mapping, RPE mapping, and a collapsed detail editor.
- Browser console: no warnings or errors; document width equals viewport width.
- Automated verification: all 52 tests passed; the final targeted two-page render check also passed.
- Intentional difference: raw Garmin activity names remain source data and are not automatically translated.
- Final result for this extension: passed.

## Desktop readability and metric explainability — 2026-08-20

- Source visual truth: user-supplied desktop screenshot and the saved Hybrid Athlete desktop handoff.
- Implementation: browser-rendered `http://127.0.0.1:4173/` after the readability and explainability pass.
- Viewports: 1920 × 1080 and 1280 × 1080 CSS px, dark mode, device scale controlled by the in-app browser.
- State: `Ma`, `Trendek`, `Cél` and `Napló`; the `Ma` view was also tested with a focused KPI tooltip.
- Full-view evidence: at 1920 px the sidebar, dashboard grid and right rail fit without horizontal overflow; the bundled Hybrid Athlete SVG lockup is visibly rendered at 60 × 45 px.
- Focused evidence: keyboard focus on the weekly load KPI opens a plain-Hungarian tooltip explaining what the number measures, why it matters and how to interpret higher values. Trend cards expose distinct CTL, ATL, TSB, training-frequency and RPE explanations. Numeric journal headers expose explanations even before rows load.

### Required fidelity surfaces

- Fonts and typography: 1920 px targets are 34 px page title, 16 px navigation, 15 px metric labels, 21–25 px KPI values and at least 11–12 px compact metadata. At 1280 px the corresponding minimums are 32, 15 and 14 px.
- Spacing and layout: 1280–1399 px now changes to a single-column primary dashboard with a two-column secondary rail, avoiding the previous horizontal overflow. The 1920 px two-column hierarchy is preserved.
- Colors and tokens: tooltips use the existing obsidian, border and user-selected accent tokens; no new competing color system was introduced.
- Image quality: the supplied logo SVG is imported into the Vite bundle as a data asset, eliminating deployment-path dependency while preserving vector sharpness.
- Copy and content: explanations are Hungarian and use non-clinical, non-causal language. They state meaning, practical impact and interpretation limits.

### Accessibility and interaction

- Every generated explanation target receives `tabindex="0"` and a complete Hungarian `aria-label`.
- Tooltips open on hover, focus and focus-within; visible focus rings use the active accent.
- Tested pages: `Ma` 12 explanation targets, `Trendek` 7, `Cél` 8; `Napló` always exposes five numeric header explanations and adds cell-level explanations when activity rows exist.
- Browser console: no errors.
- Automated verification: full navigation test, 4 Sites packaging tests and production build passed.

### Comparison history

- Initial P1: the desktop readability layer was loaded before the base stylesheet and was overwritten, leaving 9–12 px text at large widths. Fixed by loading it last and adding explicit 1080/1400 px minimums.
- Initial P1: the logo depended on a public path and was reported missing in deployment. Fixed by bundling the supplied SVG through Vite and using that asset in the sidebar and onboarding.
- Initial P2: KPI tooltip positioning caused horizontal overflow at the right rail. Fixed with right-aligned tooltip anchoring and a 1280–1399 px layout breakpoint.
- Post-fix evidence: no horizontal overflow at 1280 or 1920 px, bundled logo has a non-zero natural size, keyboard tooltip display is `block`, and no console errors remain.

final result: passed

## Brand asset integration — 2026-08-20

- Source visual truth: `C:/Users/User/Documents/ChatGPT/Garmin/.design-import-mobile/design_handoff_hybrid_athlete/screenshots/desktop/01-ma-fresh.png`.
- Source asset truth: `C:/Users/User/Documents/ChatGPT/Garmin/.design-import-mobile/design_handoff_hybrid_athlete/assets/`.
- Browser-rendered implementation: `C:/Users/User/Documents/ChatGPT/Garmin/output/brand-main-1920x1180.png`.
- Combined comparison: `C:/Users/User/Documents/ChatGPT/Garmin/output/brand-design-comparison.png`.
- State: desktop dark-mode `Ma` view after completed onboarding, local API unavailable with intentional demo fallback.
- Browser viewport: 1920 × 1180 CSS px; captured app pixels: 1920 × 1065 at device scale factor 1. Source pixels: 919 × 540. For the combined evidence, the implementation was aspect-filled and cropped to the source export size; browser presentation chrome was excluded from product findings.

### Full-view and focused comparison

The full-view comparison confirms the source hierarchy remains intact while the supplied production mark, desktop grid/tint background and header motifs now provide the intended brand signature. Focused inspection covered the sidebar lockup, `Ma` header, onboarding icon and empty-state asset placement; no generated, placeholder or CSS-drawn substitute remains for those supplied assets.

### Required fidelity surfaces

- Fonts and typography: Geist and Geist Mono hierarchy is unchanged and remains aligned with the handoff.
- Spacing and layout rhythm: the brand assets are decorative layers and do not shift the established desktop card grid, sidebar width or control sizing.
- Colors and visual tokens: supplied SVGs use the handoff teal/obsidian palette; the UI's user-selected accent still controls functional highlights.
- Image quality and asset fidelity: original production SVGs are used directly for the logo, icon, shell, view motifs and empty states, preserving vector sharpness.
- Copy and content: the document language and title are now Hungarian/Hybrid Athlete; live data and Hungarian product copy remain unchanged.

### Interaction and runtime evidence

- Primary interactions tested in the in-app browser: onboarding completion and navigation through `Naptár`, `Trendek`, `Insights`, `Napló`, `Profil`, then back to `Ma`.
- Asset checks: the production logo URL and desktop-shell computed background URL were verified in the rendered DOM.
- Browser console: no warnings or errors after the final reload and navigation pass.
- Automated checks: production build passed, 4 Sites packaging tests passed, and the full navigation test passed.

### Comparison history

- Initial pass found one P2 presentation issue: a raw JSON parse failure was shown in the top bar when the optional local API was unavailable.
- Fix: replaced the raw exception with a concise Hungarian demo-fallback status and repeated the browser capture.
- Post-fix evidence: `output/brand-main-1920x1180.png`; no actionable P0/P1/P2 visual differences remain for this scoped brand integration.

### Follow-up polish

- P3: add the supplied light-mode logo variant when the currently visual-only theme button receives full theme behavior.

final result: passed

## Desktop logo-lockup correction — 2026-08-20

- Source visual truth: `frontend/public/brand/logo/mark-onDark.svg` and the saved Hybrid Athlete desktop handoff.
- Browser-rendered implementation: in-app browser capture of `http://127.0.0.1:4173/`, desktop dark-mode `Ma` view.
- Viewport: 1264 × 712 CSS px at device scale factor 1; focused logo region measured 199.2 × 39 px, with the original SVG rendered at 52 × 39 px.
- State: expanded sidebar, completed visual load; compact sidebar was also exercised.
- Full-view evidence: the logo now leads the sidebar hierarchy at native aspect ratio and remains distinct from navigation icons.
- Focused evidence: original SVG mark, `HYBRID ATHLETE` wordmark and `SZEMÉLYES EDZÉSDÖNTÉS` descriptor render as one lockup; collapsed mode keeps a 45 × 34 px source mark without text clipping.
- Fonts and typography: Geist Mono wordmark, 13 px/0.17 em desktop treatment, white primary and muted descriptor.
- Spacing/layout: 13 px mark-to-copy gap; no collision with collapse control or first navigation item.
- Colors/tokens: original white/teal SVG colors preserved; no CSS recoloring or substitute artwork.
- Image quality: supplied vector asset is used directly and remains sharp at both sizes.
- Copy/content: official product name and Hungarian descriptor are unchanged.
- Primary interactions tested: expanded and collapsed sidebar states.
- Browser console: no errors.
- Comparison history: the earlier implementation rendered the mark in a square 36–42 px slot and it read as a tiny decoration (P2). The fix restores the native ratio, enlarges it to 52–60 px desktop width, and defines an explicit compact state. No actionable P0/P1/P2 finding remains.

final result: passed

## Secondary-view extension — Trendek és Insights

- Source visuals: `05-trendek.png` and `06-insights.png` from the saved Hybrid Athlete desktop handoff.
- Implementation captures: `output/trends-qa.png` and `output/insights-qa.png`.
- Combined evidence: `output/trends-comparison.png` and `output/insights-comparison.png`.
- Viewport: 1920 × 1180, dark mode, deterministic demo history.
- Trendek: the implementation matches the reference hierarchy with a 90-day ATL/CTL/TSB hero chart, five-zone time distribution, and cardio/strength/musculoskeletal load composition. Detailed recovery signals, methodology and RPE editing remain available in collapsed secondary panels.
- Insights: findings lead the page with statement, strength bar, sample size, Spearman rho and confidence; weekly KPIs, the deload/taper recommendation and drift status follow before the existing technical validation and model lifecycle tools.
- Intentional differences: live analytics determine the values and number of findings; the design's locked sample insight is omitted because the local application has no entitlement model. Existing model-validation tools are retained below the design-led summary.
- Browser console: no warnings or errors. Document width equals the 1920 px viewport; no horizontal overflow.
- Automated verification: all 52 tests passed.
- Remaining P3 polish: a future entitlement feature may add the reference's locked insight card; a future layout pass may move the deload recommendation into a persistent right rail when the Streamlit shell supports that without duplicating analytics logic.
- Final result for this extension: passed.
