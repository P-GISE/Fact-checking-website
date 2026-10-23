# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim
ARG FACTLENS_SOURCE_REVISION=unknown
ARG FACTLENS_BRIDGE_BASE=none
LABEL io.factlens.migration-control="v1" org.opencontainers.image.revision=$FACTLENS_SOURCE_REVISION io.factlens.bridge-base=$FACTLENS_BRIDGE_BASE
WORKDIR /app
COPY package*.json ./
COPY apps/api/package.json apps/api/package.json
COPY apps/web/package.json apps/web/package.json
RUN --mount=type=secret,id=proxy_ca NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --no-audit --no-fund
COPY apps/api apps/api
RUN npm run build --workspace apps/api
RUN chmod -R a+rX /app
USER node
ENV NODE_ENV=production API_HOST=0.0.0.0 MEDIA_ROOT=/data/media
CMD ["node","apps/api/dist/server.js"]
