# Build from the repository root: docker build -f frontend/Dockerfile .

# Stage 1: Install dependencies
FROM node:22-alpine AS deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Stage 2: Build
FROM node:22-alpine AS build
WORKDIR /app/frontend
COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend/ ./
# Production code imports only these design-system files. Reference material is
# deliberately quarantined and must never enter an image stage.
COPY design-system/package.json /app/design-system/package.json
COPY design-system/src/ /app/design-system/src/
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_IDENTITY_MODE=demo
ARG NEXT_PUBLIC_ENTRA_TENANT_ID=
ARG NEXT_PUBLIC_ENTRA_CLIENT_ID=
ARG NEXT_PUBLIC_ENTRA_API_CLIENT_ID=
ARG NEXT_PUBLIC_ENTRA_API_SCOPES=
ARG NEXT_PUBLIC_ENTRA_REDIRECT_URI=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_IDENTITY_MODE=$NEXT_PUBLIC_IDENTITY_MODE
ENV NEXT_PUBLIC_ENTRA_TENANT_ID=$NEXT_PUBLIC_ENTRA_TENANT_ID
ENV NEXT_PUBLIC_ENTRA_CLIENT_ID=$NEXT_PUBLIC_ENTRA_CLIENT_ID
ENV NEXT_PUBLIC_ENTRA_API_CLIENT_ID=$NEXT_PUBLIC_ENTRA_API_CLIENT_ID
ENV NEXT_PUBLIC_ENTRA_API_SCOPES=$NEXT_PUBLIC_ENTRA_API_SCOPES
ENV NEXT_PUBLIC_ENTRA_REDIRECT_URI=$NEXT_PUBLIC_ENTRA_REDIRECT_URI
RUN npm run build

# Stage 3: Runtime
FROM node:22-alpine AS runtime
WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=build /app/frontend/public ./frontend/public
COPY --from=build --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/frontend/.next/static ./frontend/.next/static

WORKDIR /app/frontend
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
