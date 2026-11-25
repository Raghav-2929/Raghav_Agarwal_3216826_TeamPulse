# TeamPulse web (SvelteKit static SPA) — served by unprivileged nginx.
#
# Build context is ./frontend so both packages are visible:
#   docker build -f frontend/web/Dockerfile -t teampulse-web ./frontend
#   docker run -p 8080:8080 teampulse-web          # expects the gateway at http://gateway:8000
#
# Optional build arg: PUBLIC_API_BASE_URL (default empty = same-origin /api, proxied by nginx).

# ---------------------------------------------------------------- build
FROM node:22-alpine AS build
WORKDIR /app

# 1) Component library (@teampulse/ui-components) — consumed by the web app as a package
COPY ui-components/package.json ui-components/package-lock.json ./ui-components/
RUN cd ui-components && npm ci --no-audit --no-fund
COPY ui-components/ ./ui-components/
RUN cd ui-components && npm run build

# 2) Web app (depends on "file:../ui-components")
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci --no-audit --no-fund
COPY web/ ./web/
ARG PUBLIC_API_BASE_URL=""
ENV PUBLIC_API_BASE_URL=${PUBLIC_API_BASE_URL}
RUN cd web && npm run build

# ---------------------------------------------------------------- runtime
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/web/build /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
