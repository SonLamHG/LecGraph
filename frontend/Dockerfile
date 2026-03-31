# --- Build stage ---
FROM node:22-alpine AS builder

WORKDIR /app

# Layer 1: Install deps (cached if package.json unchanged)
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Layer 2: Build app
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Production stage ---
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy only standalone output
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
