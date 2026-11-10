# Builds the React app and serves it with Caddy, which also proxies /api to the backend
# and obtains TLS certificates from Let's Encrypt automatically.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
