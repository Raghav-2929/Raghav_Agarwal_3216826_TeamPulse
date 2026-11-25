# @teampulse/ui-components

Framework-agnostic web components and **central design tokens** for TeamPulse, built with
[StencilJS](https://stenciljs.com) v4. Shadow DOM, accessible, keyboard-friendly and responsive.
Consumed by the SvelteKit dashboard (`frontend/web`) as a regular npm package.

| Tag | Purpose |
|---|---|
| [`tp-leaderboard-table`](#tp-leaderboard-table) | Individual / team challenge leaderboards |
| [`tp-progress-ring`](#tp-progress-ring) | Circular progress (ARIA progressbar) |
| [`tp-progress-card`](#tp-progress-card) | Habit / streak card with meter and action |
| [`tp-trend-chart`](#tp-trend-chart) | Pure-SVG line/bar trend chart with gaps for suppressed days |
| [`tp-badge`](#tp-badge) | Earned / locked achievement badge |
| [`tp-stat-tile`](#tp-stat-tile) | KPI tile with delta |

## Install

```bash
npm install @teampulse/ui-components
```

```js
// 1. Design tokens — load once at the app root
import '@teampulse/ui-components/tokens.css';

// 2a. Bundlers (Vite, webpack…): tree-shakable self-registering custom elements
import { defineCustomElements } from '@teampulse/ui-components/components';
defineCustomElements();

// 2b. …or the lazy loader (plain HTML / CDN)
import { defineCustomElements } from '@teampulse/ui-components/loader';
defineCustomElements(window);
```

Register the elements **before** your framework renders them. Frameworks such as Svelte 5 then
detect the elements' property setters and pass arrays/objects as DOM *properties*.

## Design tokens

`tokens.css` (source: `src/global/tokens.css`) is the single source of truth for colour, spacing,
radius, typography, elevation and motion. Every component styles itself **only** with these
`--tp-*` custom properties, which inherit through shadow roots.

| Group | Examples |
|---|---|
| Brand / semantic | `--tp-color-primary`, `-primary-hover`, `-primary-contrast`, `-primary-soft`, `--tp-color-success / warning / danger / info (+ -soft)` |
| Surfaces & text | `--tp-color-bg`, `--tp-color-surface`, `-surface-muted`, `-surface-hover`, `--tp-color-border(-strong)`, `--tp-color-text(-muted/-subtle/-inverse)`, `--tp-color-focus-ring` |
| Activity types | `--tp-color-category-fitness`, `-mindfulness`, `-nutrition`, `-sleep`, `-hydration`, `-learning` |
| Charts | `--tp-chart-1` … `--tp-chart-6`, `--tp-chart-grid`, `--tp-chart-axis`, `--tp-chart-gap` |
| Spacing | `--tp-space-0 … --tp-space-12` (4 px grid) |
| Radius | `--tp-radius-sm / md / lg / xl / pill` |
| Typography | `--tp-font-family-sans / mono`, `--tp-font-size-xs … 3xl`, `--tp-font-weight-*`, `--tp-line-height-*` |
| Elevation / motion | `--tp-shadow-sm / md / lg`, `--tp-duration-fast / normal / slow`, `--tp-easing-standard`, `--tp-focus-ring` |

**Theming** — light by default; dark follows `prefers-color-scheme: dark`. Force a theme with
`<html data-theme="light">` or `<html data-theme="dark">`. `prefers-reduced-motion` zeroes durations.

## Passing data: properties *and* attributes

Array props accept a JS array (property — preferred) **or** a JSON string (attribute fallback).
Invalid JSON renders the empty state instead of throwing.

```html
<tp-leaderboard-table entries='[{"rank":1,"display_name":"Alice","score":12}]'></tp-leaderboard-table>
<script>document.querySelector('tp-leaderboard-table').entries = rows;</script>
```

## Events and how to listen to them (Svelte 5 pattern)

All custom events are **dash-cased, prefixed `tp-`**, and dispatched with `bubbles: true, composed: true`:

| Event | Emitted by | `detail` |
|---|---|---|
| `tp-row-select` | `tp-leaderboard-table` | `{ index, mode: 'individual' \| 'team', entry }` |
| `tp-point-select` | `tp-trend-chart` | `{ index, x, values: [{ label, y }] }` |
| `tp-action` | `tp-progress-card` | `{ action }` (the `action` prop, default `"complete"`) |

**Svelte 5** — event attributes are case-sensitive and use the event name verbatim after `on`, so
write `ontp-<event>` (do *not* camel-case it — `onTpRowSelect` would listen for `TpRowSelect`):

```svelte
<tp-leaderboard-table entries={rows} highlightMe={true} ontp-row-select={(e) => select(e.detail)}></tp-leaderboard-table>
<tp-progress-card heading="Run" actionLabel="Mark complete" ontp-action={() => complete()}></tp-progress-card>
<tp-trend-chart series={series} ontp-point-select={(e) => show(e.detail)}></tp-trend-chart>
```

This pattern is verified by a Vitest + jsdom test in the web app
(`frontend/web/src/lib/ui/custom-events.svelte.test.ts`) that mounts a real Svelte 5 component
rendering these built elements, asserts arrays arrive as properties (same instance, no attribute) and
that clicks inside the shadow DOM reach the `ontp-…` handlers. TypeScript typings for Svelte
templates live in `frontend/web/src/lib/ui/elements.d.ts` (built from this package's `Components`
types). Plain DOM: `el.addEventListener('tp-row-select', (e) => …)`. The names are also exported
as `TP_EVENTS`.

---

## Components

### `tp-leaderboard-table`

Ranked table with podium medals (1–3), "You" highlight, and keyboard navigation
(↑/↓/Home/End to move, Enter/Space to select). Secondary columns hide in narrow containers.

| Prop (attribute) | Type | Default | Description |
|---|---|---|---|
| `entries` (`entries`) | `LeaderboardEntry[] \| TeamLeaderboardEntry[] \| string` | `[]` | Individual rows `{rank, display_name, team_name?, score, goal_reached?, is_me?}` or team rows `{rank, team_name, participants, total_score, average_score}` |
| `mode` (`mode`) | `'individual' \| 'team'` | `'individual'` | Column set |
| `highlightMe` (`highlight-me`) | `boolean` | `true` | Highlight the `is_me` row (`aria-current`) |
| `emptyText` (`empty-text`) | `string` | `'No participants yet.'` | Empty-state message |
| `caption` (`caption`) | `string` | `'Leaderboard'` | Accessible (visually hidden) table caption |
| `scoreLabel` (`score-label`) | `string` | `'Score'` | Score column header (individual mode) |

Events: `tp-row-select`. Slots: `caption` (header title), `actions` (header controls).
Parts: `table`, `row`.

### `tp-progress-ring`

| Prop (attribute) | Type | Default | Description |
|---|---|---|---|
| `value` | `number` | `0` | Current value |
| `max` | `number` | `100` | Value representing 100 % |
| `size` | `number` | `120` | Diameter (px) |
| `strokeWidth` (`stroke-width`) | `number` | `10` | Ring thickness (px) |
| `label` | `string` | `'Progress'` | Accessible name |
| `tone` | `primary \| success \| warning \| danger \| neutral \| <category>` | `'primary'` | Colour (categories map to `--tp-color-category-*`) |

Renders `role="progressbar"` with `aria-valuenow/min/max/valuetext`. Default slot: centre content
(defaults to the rounded percentage). Parts: `ring`, `center`.

### `tp-progress-card`

| Prop (attribute) | Type | Default | Description |
|---|---|---|---|
| `heading` | `string` | `''` | Title (`title` is a reserved global attribute) |
| `value` / `target` | `number` | `0` / `0` | Meter figures; no meter when `target` is 0 |
| `unit` | `string` | `''` | Unit after the figures |
| `streak` | `number` | `0` | Streak length; hidden when 0 |
| `streakUnit` (`streak-unit`) | `string` | `'day'` | `day` / `week` |
| `category` | `string` | – | Accent colour + default icon |
| `completed` | `boolean` (reflected) | `false` | Completed state; disables the action |
| `actionLabel` (`action-label`) | `string` | `''` | Built-in button label (hidden when empty) |
| `completedLabel` (`completed-label`) | `string` | `'Done'` | Button label once completed |
| `action` | `string` | `'complete'` | Value sent in the event detail |
| `busy` | `boolean` | `false` | Busy state (`aria-busy`, disables the action) |

Events: `tp-action`. Slots: default (body), `icon`, `actions`. Parts: `card`, `action`.

### `tp-trend-chart`

Dependency-free SVG chart. `null` y values are **gaps**: lines break and a hatched marker plus a
legend entry (`gap-label`) explain them — used for k-anonymity–suppressed team days. Columns are
hover- and keyboard-focusable (one roving tab stop, ←/→/Home/End, Enter/Space) with a tooltip, and
a visually hidden data table mirrors the data for screen readers. Resizes with its container.
Non-date x labels (e.g. team names) are supported. Integer data gets integer y-axis steps.

| Prop (attribute) | Type | Default | Description |
|---|---|---|---|
| `series` | `TrendSeries[] \| string` | `[]` | `{label, points: [{x: 'YYYY-MM-DD', y: number \| null}], color?}` |
| `type` | `'line' \| 'bar'` | `'line'` | Chart type |
| `height` | `number` | `240` | Height (px) |
| `yLabel` (`y-label`) | `string` | `''` | Y-axis title |
| `label` | `string` | `'Trend chart'` | Accessible name |
| `emptyText` (`empty-text`) | `string` | `'No data for this period.'` | Empty state |
| `gapLabel` (`gap-label`) | `string` | `'No data'` | Text for null points |
| `showLegend` (`show-legend`) | `boolean` | `true` | Legend visibility |

Events: `tp-point-select`. Parts: `svg`, `tooltip`, `legend`.

### `tp-badge`

| Prop (attribute) | Type | Default | Description |
|---|---|---|---|
| `icon` | `string` | `'🏅'` | Emoji / short text |
| `name` | `string` | `''` | Badge name |
| `description` | `string` | `''` | What it is awarded for |
| `awardedAt` (`awarded-at`) | `string` | `''` | ISO date/datetime (shown as local date) |
| `locked` | `boolean` (reflected) | `false` | Greyed out with a lock |
| `compact` | `boolean` (reflected) | `false` | Icon + name only |

Parts: `badge`, `medal`.

### `tp-stat-tile`

| Prop (attribute) | Type | Default | Description |
|---|---|---|---|
| `label` | `string` | `''` | What is measured |
| `value` | `string \| number` | `''` | The figure (`–` when empty) |
| `delta` | `string \| number` | – | Change; numbers get a sign, strings shown as-is (`+12%`) |
| `invertDelta` (`invert-delta`) | `boolean` | `false` | A decrease is good |
| `hint` | `string` | `''` | Secondary text |

Slots: default (after the value), `icon`. Parts: `tile`, `value`.

Generated per-component API docs (from JSDoc) are in `src/components/*/readme.md`.

---

## Development

```bash
npm install
npm start        # playground at http://localhost:3333 (src/index.html)
npm run build    # dist/ (lazy + custom elements + types), loader/, dist/tokens.css, readmes
npm test         # Stencil spec tests (Jest): stencil test --spec
```

Build outputs: `dist` (lazy loader, `loader/`), `dist-custom-elements` (`dist/components`, runtime
bundled in, so consumers do not need `@stencil/core`), `docs-readme`, `www`. `scripts/copy-tokens.cjs`
(npm `postbuild`) publishes `dist/tokens.css`.

## Publishing to npm

The package is publish-ready (`version`, `files`, `exports`, `types`, `publishConfig.access=public`).

```bash
npm login                            # an account with rights to the @teampulse scope
npm version minor                    # semver: patch = fixes, minor = new props/components, major = breaking API/token changes
# update CHANGELOG.md
npm publish                          # prepublishOnly: clean → build → test
```

Consumers then switch from the local link to the registry version:
`"@teampulse/ui-components": "^1.0.0"` (see `frontend/web/README.md`).

See [CHANGELOG.md](./CHANGELOG.md) for release notes. The data shapes mirror the REST contract in
[`docs/api-contract.md`](../../docs/api-contract.md).
