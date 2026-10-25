FROM node:24-alpine AS builder

RUN corepack enable
WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/pattern ./packages/pattern
RUN pnpm install --frozen-lockfile

COPY apps/web ./apps/web
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG API_PROXY_TARGET=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV API_PROXY_TARGET=$API_PROXY_TARGET
RUN pnpm --filter @jhworks/web build
# Next.js' standalone tracer keeps pnpm's @swc/helpers symlink but can omit
# helper modules that are loaded dynamically at runtime. Restore the complete
# package inside the traced tree so the image does not contain a dangling,
# partially populated dependency.
RUN cp -R /workspace/node_modules/.pnpm/@swc+helpers@*/node_modules/@swc/helpers/. \
    /workspace/apps/web/.next/standalone/node_modules/.pnpm/@swc+helpers@*/node_modules/@swc/helpers/

FROM node:24-alpine AS runner

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app
COPY --from=builder --chown=node:node /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=node:node /workspace/apps/web/public ./apps/web/public

EXPOSE 3000
USER node
CMD ["node", "apps/web/server.js"]
