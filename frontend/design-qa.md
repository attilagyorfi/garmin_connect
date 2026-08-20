# Hybrid Athlete React migration — design QA

## Evidence

- Source visual truth: desktop references `01-ma-fresh.png`, `04-naptar.png`, `05-trendek.png`, `06-insights.png` and `07-naplo.png` under `C:/Users/User/.codex/state/plugins/product-design/assets/hybrid-athlete-desktop/`.
- Intended implementation URL: `http://localhost:4173/`
- Target viewport: 1920 × 1180, desktop dark mode, fresh daily-decision state.
- Source pixels: 919 × 540.
- Implementation screenshot: unavailable because the in-app browser runtime could not establish its trusted local connection.

## Findings

- [P0] Browser-rendered comparison is unavailable.
  - Location: full React prototype.
  - Evidence: the production build and HTTP preview succeed, but a browser screenshot could not be captured through the required in-app browser surface.
  - Impact: typography, layout rhythm, token fidelity, icon alignment, interactions and responsive behavior cannot be certified against the source image.
  - Fix: restore the in-app browser connection, capture the implementation at 1920 × 1180, create a normalized side-by-side comparison, and iterate on all P0/P1/P2 differences.

## Required fidelity surfaces

- Fonts and typography: implemented with Geist and Geist Mono; visual verification blocked.
- Spacing and layout rhythm: implemented from the 236 px sidebar and two-column source proportions; visual verification blocked.
- Colors and tokens: near-black, obsidian and `#14B8A6` token mapping implemented; visual verification blocked.
- Image quality and assets: the source contains no photography; UI icons use Lucide and the readiness ring uses Recharts. Visual verification blocked.
- Copy and content: Hungarian copy is implemented across Ma, Naptár, Trendek, Insights and Napló; visual verification blocked.

## Primary interactions implemented

- Sidebar navigation and collapse.
- Daily check-in selection and saved state.
- Recommendation rationale modal.
- Calendar day selection and detail state.
- Trend time-range selection.
- Insight recommendation acceptance.
- Journal modality filtering and text search.
- Responsive desktop/tablet/mobile layout rules.

## Automated verification

- `npm run build`: passed after the five-screen migration; chart code is split into a dedicated production chunk.
- `npm run test:sites`: 4 tests passed.
- Local HTTP preview: 200 OK.

## Comparison history

- Iteration 1: blocked before visual comparison because browser-rendered evidence is unavailable.
- Readability iteration: user reported that the desktop typography, icons and cards were too small. Desktop navigation was raised to 14 px, body/table content to 12–14 px, compact metadata to 9–11 px, icons to 18–20 px, controls to 38–48 px, and card padding/major component dimensions were increased. Build and hosting tests pass; browser-rendered comparison remains blocked.

final result: blocked
# Current desktop sizing audit — 2026-08-18

- Reference: user screenshot at 1713 × 1224 (`codex-clipboard-4dca0179-32ea-4f34-85aa-1ccdc2ef7d92.png`).
- P1 finding: dashboard cards occupied only the upper portion of the viewport, leaving excessive unused vertical space.
- P1 finding: card body copy, metadata, icons, scale controls and insight descriptions remained too small for comfortable desktop reading.
- Implemented: a native large-desktop scale for viewports at least 1400 × 850, including 14–16 px content typography, 22–24 px icons, 40–48 px controls, larger recommendation ring, and viewport-filling card rows.
- Visual re-check: pending a refreshed user screenshot because automated in-app browser inspection is currently unavailable in this environment.
