FROM node:22-bookworm-slim AS dependencies

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.5.1 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-bookworm-slim AS builder

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.5.1 --activate
COPY --from=dependencies /app/node_modules ./node_modules
COPY package.json pnpm-lock.yaml ./
COPY . .
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8123
ARG NEXT_PUBLIC_ASSISTANT_ID=chat_ui
ARG NEXT_PUBLIC_DOCKER_BROKER_URL=http://127.0.0.1:8766/v1/coder/confirmations
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_ASSISTANT_ID=$NEXT_PUBLIC_ASSISTANT_ID
ENV NEXT_PUBLIC_DOCKER_BROKER_URL=$NEXT_PUBLIC_DOCKER_BROKER_URL
RUN pnpm build

FROM node:22-bookworm-slim AS runtime

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.5.1 --activate
COPY --from=builder /app ./
EXPOSE 3000
CMD ["pnpm", "start", "--", "-p", "3000"]
