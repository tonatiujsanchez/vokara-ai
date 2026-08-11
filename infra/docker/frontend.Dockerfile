# syntax=docker/dockerfile:1
#
# Imagen del frontend: compila la SPA y sirve los estáticos.
# El contexto de build es la raíz del repositorio.

# ── build ─────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# npm ci exige el lock y lo respeta al pie de la letra (ADR-000).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── runtime ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
