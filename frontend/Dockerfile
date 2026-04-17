# ─────────────────────────────────────────────────────────────────
#  RafaelPabonAirlines — Frontend (React + Vite → nginx)
#  Build multi-stage: compila con Node, sirve con nginx alpine.
# ─────────────────────────────────────────────────────────────────

# ── Etapa 1: build ────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .
RUN npm run build

# ── Etapa 2: servidor estático ────────────────────────────────
FROM nginx:1.27-alpine

# Configuración SPA (todas las rutas → index.html)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Artefactos del build
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
