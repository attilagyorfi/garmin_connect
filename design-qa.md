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
