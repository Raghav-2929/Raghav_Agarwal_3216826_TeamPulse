# Changelog

All notable changes to `@teampulse/ui-components` are documented here.
The project follows [Semantic Versioning](https://semver.org/) and the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

- **MAJOR** — breaking change to a tag name, prop, attribute, event name/detail, slot, part or token name.
- **MINOR** — new component, prop, event, slot, part or token (backwards compatible).
- **PATCH** — bug fixes and visual tweaks that keep the public API intact.

## [Unreleased]

## [1.0.0] - 2026-11-08

### Added

- Central design tokens (`tokens.css`, exported as `@teampulse/ui-components/tokens.css`): brand,
  semantic, surface, text, category (fitness, mindfulness, nutrition, sleep, hydration, learning),
  chart palette, spacing, radius, typography, elevation and motion — light + dark
  (`prefers-color-scheme`, overridable with `data-theme`).
- `tp-leaderboard-table` — individual/team leaderboards, podium medals, "You" highlight,
  keyboard row navigation, `tp-row-select` event, `caption` / `actions` slots.
- `tp-progress-ring` — SVG ring with ARIA `progressbar` semantics and a centre slot.
- `tp-progress-card` — habit/streak card with meter, streak, `icon` / `actions` / default slots
  and a `tp-action` event from the built-in action button.
- `tp-trend-chart` — dependency-free SVG line/bar chart; `null` points render as gaps
  (k-anonymity–suppressed days), keyboard + hover tooltips, `tp-point-select` event,
  screen-reader data table.
- `tp-badge` — earned/locked achievement badge.
- `tp-stat-tile` — KPI tile with delta direction and hint.
- Array props accept JS arrays (property) or JSON strings (attribute).
- Build outputs: lazy loader (`dist` + `loader/`) and tree-shakable custom elements (`dist/components`).
