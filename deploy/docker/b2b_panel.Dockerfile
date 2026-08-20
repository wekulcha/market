FROM node:20-alpine AS build

WORKDIR /app
COPY b2b_panel/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi

COPY b2b_panel/ ./

ARG VITE_API_URL=/api
ARG VITE_ASSET_BASE_URL=/b2b-static/
ENV VITE_API_URL=${VITE_API_URL} \
    VITE_ASSET_BASE_URL=${VITE_ASSET_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/b2b_spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
