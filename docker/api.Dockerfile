# syntax=docker/dockerfile:1
FROM node:24-alpine3.24 AS build
WORKDIR /app
COPY package*.json ./
COPY apps/api/package.json apps/api/package.json
COPY apps/web/package.json apps/web/package.json
RUN --mount=type=secret,id=proxy_ca NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --no-audit --no-fund
COPY apps/api apps/api
RUN npm run build --workspace apps/api

FROM node:24-alpine3.24 AS production-dependencies
WORKDIR /app
COPY package*.json ./
COPY apps/api/package.json apps/api/package.json
COPY apps/web/package.json apps/web/package.json
RUN --mount=type=secret,id=proxy_ca NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --omit=dev --workspace apps/api --include-workspace-root --no-audit --no-fund

FROM node:24-alpine3.24
ARG FACTLENS_SOURCE_REVISION=unknown
ARG FACTLENS_BRIDGE_BASE=none
LABEL io.factlens.migration-control="v1" org.opencontainers.image.revision=$FACTLENS_SOURCE_REVISION io.factlens.bridge-base=$FACTLENS_BRIDGE_BASE
RUN --mount=type=secret,id=proxy_ca,target=/etc/apk/ca.pem apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules /opt/yarn-* \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn /usr/local/bin/yarnpkg /usr/local/bin/corepack
WORKDIR /app
COPY --from=production-dependencies /app/node_modules ./node_modules
COPY --from=production-dependencies /app/apps/api ./apps/api
COPY --from=build /app/apps/api/dist ./apps/api/dist
COPY apps/api/migrations ./apps/api/migrations
RUN chmod -R a+rX /app
USER node
ENV NODE_ENV=production API_HOST=0.0.0.0 MEDIA_ROOT=/data/media
CMD ["node","apps/api/dist/server.js"]
