FROM node:20-alpine AS builder

WORKDIR /app

COPY node-gateway/package.json ./
RUN npm install

COPY node-gateway/tsconfig.json ./
COPY node-gateway/src/ ./src/

RUN npm run build

# --- Production stage ---
FROM node:20-alpine

WORKDIR /app

RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

COPY node-gateway/package.json ./
RUN npm install --omit=dev && npm cache clean --force

COPY --from=builder /app/dist ./dist
COPY proto/ /proto/

USER appuser

EXPOSE 3000 3001

CMD ["node", "dist/index.js"]
