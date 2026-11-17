# SART · imagen de la web (RNF-P-1): se compila con Node y se sirve con nginx, que reenvía /api a la API.
# Mismo origen para la cookie httpOnly de la sesión (RNF-S-1), como el proxy de Vite en desarrollo.
FROM node:22-alpine AS compilacion
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=compilacion /web/dist /usr/share/nginx/html
EXPOSE 80
