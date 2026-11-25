# TeamPulse frontend

| Package | Path | What |
|---|---|---|
| `@teampulse/ui-components` | [`ui-components/`](./ui-components) | StencilJS web-component library + central design tokens (publishable to npm) |
| `@teampulse/web` | [`web/`](./web) | SvelteKit (Svelte 5 runes) SPA consuming the library as a package |

Both code against the REST contract in [`docs/api-contract.md`](../docs/api-contract.md).

## Prerequisites

Node 20+ (developed with Node 24 / npm 11). The backend gateway on `http://localhost:8000` for the
running app (not needed for builds or tests).

## Setup, run, build, test

```bash
# component library
cd frontend/ui-components
npm install
npm run build          # dist/, loader/, dist/tokens.css
npm test               # Stencil spec tests (Jest)

# web app
cd ../web
npm install            # links @teampulse/ui-components from ../ui-components
npm run dev            # http://localhost:5173 (proxies /api and /.well-known to :8000)
npm run check          # svelte-check
npm run build          # static SPA in build/
npx vitest run         # unit + jsdom tests
```

Environment variables (`web/.env.example`): `PUBLIC_API_BASE_URL` (default empty = same origin) and
`TEAMPULSE_GATEWAY_URL` (dev/preview proxy target, default `http://localhost:8000`).

## How the library is consumed

`web/package.json` has `"@teampulse/ui-components": "file:../ui-components"`: the app installs the
**built** package and only uses its public entry points (`/tokens.css`, `/components`, root types).
To use the registry version instead, publish the library and change the dependency to `"^1.0.0"` —
no code changes required (details in [`web/README.md`](./web/README.md)).

## Publishing the library to npm

```bash
cd frontend/ui-components
npm login
npm version patch|minor|major      # semantic versioning — see CHANGELOG.md
npm publish                        # prepublishOnly: clean → build → test; publishConfig.access=public
```

## Container image

`web/Dockerfile` (build context `./frontend`, see `.dockerignore`) builds both packages and serves
the SPA with unprivileged nginx on port 8080, proxying `/api/` and `/.well-known/` to
`http://gateway:8000`:

```bash
docker build -f frontend/web/Dockerfile -t teampulse-web ./frontend
```
