# TeamPulse web (SvelteKit + Svelte 5 runes)

Single-page dashboard for **employees, managers and admins**: habits, challenges, personal
insights, aggregated (k-anonymised) team insights, notifications and administration.
It consumes the `@teampulse/ui-components` web-component library **as a package** and codes against
the REST contract in [`docs/api-contract.md`](../../docs/api-contract.md).

## Quick start

```bash
# 1. build the component library once (the app consumes its built dist/)
cd ../ui-components && npm install && npm run build

# 2. run the app
cd ../web
npm install
npm run dev            # http://localhost:5173 — /api and /.well-known are proxied to http://localhost:8000
```

The backend gateway must be running on `http://localhost:8000` (override with
`TEAMPULSE_GATEWAY_URL`). Demo accounts (password `TeamPulse@2026`) are listed on the login page.

| Script | What it does |
|---|---|
| `npm run dev` | Vite dev server with the API proxy |
| `npm run check` | `svelte-kit sync` + `svelte-check` (TypeScript + Svelte diagnostics) |
| `npm run build` | Static SPA into `build/` (`index.html` fallback) |
| `npm run preview` | Serve the production build locally (also proxies `/api`) |
| `npm test` / `npx vitest run` | Vitest unit tests (+ one jsdom integration test) |
| `npm run ui:build` | Rebuild the component library |

## Environment

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `PUBLIC_API_BASE_URL` | browser (`$env/dynamic/public`, emitted to `_app/env.js` at build) | `''` | Prefix for API calls. Empty = same origin (`/api/*` on CloudFront / nginx / Vite proxy). |
| `TEAMPULSE_GATEWAY_URL` | `vite.config.ts` only | `http://localhost:8000` | Target of the dev/preview proxy. |

See `.env.example`.

## How the component library is consumed

`package.json` depends on the **built** library through a local file link:

```json
"dependencies": { "@teampulse/ui-components": "file:../ui-components" }
```

npm links `node_modules/@teampulse/ui-components` → `../ui-components`; the app imports only the
package's public entry points, never its `src/`:

- `@teampulse/ui-components/tokens.css` — central design tokens, imported once in `src/routes/+layout.svelte`.
- `@teampulse/ui-components/components` — `defineCustomElements()` (tree-shakable custom-elements
  build). `src/lib/ui/register.ts` calls it from the root `+layout.ts` **load** function (browser
  only, `ssr = false`), i.e. before any page renders, so Svelte sees the elements' property setters
  and passes arrays/objects as DOM properties.
- Types (`Components`, `TrendSeries`, `LeaderboardRowSelectDetail`, …) from the package root;
  Svelte template typings in `src/lib/ui/elements.d.ts`.

`vite.config.ts` allows `server.fs` access to `../ui-components` because the linked package lives
outside this folder. After changing the library run `npm run ui:build` and reload.

### Switching to the published npm package

```bash
npm install @teampulse/ui-components@^1.0.0     # replaces the file: link
```

i.e. `"@teampulse/ui-components": "^1.0.0"` in `package.json`. No code changes are needed — imports
use the same public entry points — and the `server.fs.allow` entry can then be removed.

### Listening to the components' events (Svelte 5)

Events are dash-cased (`tp-row-select`, `tp-point-select`, `tp-action`). Svelte 5 event attributes
are case-sensitive and take the name verbatim after `on`, so:

```svelte
<tp-leaderboard-table entries={rows} ontp-row-select={(e) => (selected = e.detail)}></tp-leaderboard-table>
```

`src/lib/ui/custom-events.svelte.test.ts` mounts a Svelte 5 component that renders the real built
elements in jsdom and verifies property passing and event delivery.

## Architecture

```
src/
  app.css                       global styles (tokens only)
  lib/
    api/        types.ts (contract types) · http.ts (fetch wrapper, bearer, 401→refresh-once, problem+json)
                errors.ts (ApiError) · endpoints.ts (typed endpoint functions) · jwt.ts · index.ts (api singleton)
    state/      session.svelte.ts · notifications.svelte.ts (60 s poll) · toasts.svelte.ts · theme.svelte.ts
                query.svelte.ts (rune-based async resource) · url-filters.svelte.ts (filters ⇄ URL)
    utils/      dates.ts (range presets) · filters.ts (URL (de)serialisation) · nav.ts (role → routes)
                validation.ts · insights.ts · categories.ts
    components/ Sidebar, TopBar, Toasts, Modal, ConfirmDialog, HabitForm, DateRangePicker, …
    ui/         register.ts (custom-element registration) · elements.d.ts (template typings)
    guards.ts   requireSession / requireRole for load functions
  routes/
    +layout.ts            ssr=false, registers the custom elements
    login/                login + demo-account quick fill
    (app)/+layout.ts      auth guard (restores the session from the refresh token)
    (app)/dashboard  habits[/new|/team|/[id]|/[id]/edit]  challenges[/new|/[id]]  analytics
    (app)/team            manager/admin guard (+layout.ts)
    (app)/admin/{users,teams,badge-rules,insights}   admin guard (+layout.ts)
    (app)/notifications  (app)/profile
```

- **Svelte 5 runes only** — `$state`, `$derived`, `$effect`, `$props`, `$bindable`; shared state in
  `.svelte.ts` modules (classes with rune fields). No `export let`, `$:` or `svelte/store`.
- **Role-based navigation** — `NAV_ITEMS` in `utils/nav.ts` maps every route to the roles that may
  see it; the sidebar renders `navForRole(role)`. Route guards in `+layout.ts`/`+page.ts` load
  functions redirect to `/login` (no session) or throw 403, rendered by `(app)/+error.svelte`
  inside the shell. The server still enforces every permission.
- **Reactive, URL-synced filters** — `createUrlFilters(schema)` parses typed filters from the query
  string, binds them to controls and writes them back with `goto(…, { replaceState, keepFocus, noScroll })`
  (debounced); `createQuery({ key, fetch, debounce })` re-fetches when the key changes, aborting
  stale requests. Used for habits (search, activity type, visibility, archived), challenges (status,
  activity type, date range, search, joined), analytics/team (date range presets + custom, activity
  type), users (search, role, team) and notifications (unread).
- **Privacy** — the team page shows an explicit privacy notice, renders suppressed days as gaps
  labelled "Suppressed (fewer than N members)" (missing days are treated as suppressed too), lists
  suppressed categories, and shows member *names only*. Activity logs and streaks of other people
  are never requested.

### Authentication & token storage (trade-off)

- Access token (15 min JWT) is kept **in memory only**; `managed_team_ids` is decoded from its claims
  (it is not part of `UserOut`).
- The refresh token is kept in **`localStorage`** so reloads/new tabs can restore the session via
  `POST /api/v1/auth/refresh`. It is readable by any script on the origin, so XSS would expose it;
  this is mitigated by server-side rotation on every refresh, revocation on logout, a strict CSP and
  no third-party scripts. The recommended hardening is an `HttpOnly; Secure; SameSite=Strict`
  refresh cookie issued by the gateway (backend change).
- On a `401` the client refreshes **once** (single-flight per tab, serialised across tabs with the
  Web Locks API so two tabs never spend the same rotating token), retries the request, and on failure
  clears the session and redirects to `/login?redirect=…`. Signing out in one tab signs out the
  others (`storage` event). A refresh interrupted mid-flight (page closed after the server rotated
  the token) can still force a re-login — inherent to rotating refresh tokens.
- Errors are RFC 7807 `problem+json`, parsed into a typed `ApiError` whose `detail` is what users see.

## Tests

`npx vitest run` runs two Vitest projects (configured in `vite.config.ts`):

- **unit** (node): `src/lib/**/*.test.ts` — date-range presets, filter ⇄ URL helpers, nav-by-role and
  route access, API error parsing, the HTTP client's refresh-once logic, JWT decoding, validation,
  insight series (suppressed days → gaps).
- **dom** (jsdom): `src/**/*.svelte.test.ts` — Svelte 5 ↔ custom-element integration.

## Deployment

`npm run build` emits a static SPA in `build/` (adapter-static, fallback `index.html`):

- **S3 + CloudFront** — upload `build/`; CloudFront error/fallback to `/index.html` for client routes,
  long-lived caching for `/_app/immutable/*`, no-cache for `index.html`, and an `/api/*` behaviour to
  the gateway (same origin, so `PUBLIC_API_BASE_URL` stays empty).
- **Container** — `Dockerfile` (build context `./frontend`):
  `docker build -f frontend/web/Dockerfile -t teampulse-web ./frontend`. It builds the library and the
  app on `node:22-alpine`, then serves `build/` from `nginxinc/nginx-unprivileged` on port 8080 using
  `nginx.conf` (SPA fallback, immutable asset caching, `/api/` and `/.well-known/` proxied to
  `http://gateway:8000`, `/healthz`).
