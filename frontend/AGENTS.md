# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Product-specific desktop rule

The primary target is a desktop application around 1920 px. Use comfortable desktop readability rather than reproducing the small apparent scale of the exported screenshots. On large desktop viewports, body and table text should normally be 14–16 px, compact metadata at least 11 px, navigation 16 px, icons 22–24 px, and primary controls 42–48 px high. The dashboard should use the available viewport height instead of clustering shallow cards at the top. Keep cards spacious and scannable while preserving the reference hierarchy.

The supplied Hybrid Athlete SVG mark must remain clearly visible as part of a full sidebar logo lockup. Preserve its native 4:3 aspect ratio, keep the wordmark readable on desktop, and retain a distinct compact mark when the sidebar is collapsed. Use the supplied mark—not a typographic placeholder or generic app tile—in onboarding and branded entry states.

The product is intended to translate professional training data for non-experts. Every visible KPI or technical abbreviation must have a plain-Hungarian explanation available on hover and keyboard focus, covering what the value measures, why it matters, and what a high/low or changing value can imply. On 1920 px desktop screens, do not allow base UI text to fall back to the original small mockup scale; navigation should be about 16 px, data labels about 14–16 px, metadata at least 11–12 px, and primary KPI values 21 px or larger.
