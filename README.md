# AstroBot Monorepo

Telegram bot + Mini App for astrology and tarot.

## Stack
- `backend`: FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis
- `bot`: aiogram worker
- `miniapp`: React + Vite + Telegram Mini Apps SDK + Framer Motion
- Production runtime: Docker Compose + Tailscale Funnel

## Implemented Features
- Natal profile + full natal map (`/v1/natal/*`)
- Daily forecast + stories mode (`/v1/forecast/*`)
- Tarot spreads endpoint (`/v1/tarot/*`)
- AI interpretation for tarot (local Ollama; on failure returns mystical fallback text)
- Telegram Mini App `startapp` routing (`sc_*`)
- Telegram `initData` signature validation on backend

## Runtime Notes
- LLM runtime supports **only Ollama** (`LLM_PROVIDER=ollama`).
- If Ollama is unavailable, tarot returns local fallback text (`local:fallback`).

## Local Development

### Quick Start (local-only, recommended)
1. Copy env:
```bash
cp .env.example .env
```
2. Start all services (Postgres + Redis + Ollama + API + bot + miniapp):
```bash
docker compose up --build
```
3. Wait until model is pulled (`ollama-pull` service), then open:
- http://localhost:8000/docs

4. Run local smoke check:
```bash
./scripts/local_smoke.sh
```
Optional:
- `STRICT_LLM=false ./scripts/local_smoke.sh` (allow fallback during quick checks)

Default local-only mode in `.env.example`:
- `LOCAL_ONLY_MODE=true`
- `ASTROLOGY_PROVIDER=swisseph`
- `TAROT_PROVIDER=local`
- `OLLAMA_BASE_URL=http://ollama:11434`
- `TRANSLATE_VIA_GOOGLE_FREE=false`

Node version for miniapp build:
- `>=20` (see `miniapp/package.json`)

### Alternative: Use host Ollama instead of Docker Ollama
```bash
ollama serve
ollama pull qwen2.5:7b
```
Then set in `.env`:
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

## Production (Own Machine + Docker + Tailscale)

Use `docker-compose.prod.yml` to run production profile:
- `miniapp` is built as static assets and served by nginx.
- nginx in `miniapp` proxies `/api/*` to backend.
- Only one external port is exposed: `8080`.
- `postgres`/`redis`/`api` remain internal (no published ports).

1. Configure `.env.prod` (required keys):
- `BOT_TOKEN`
- `BOT_USERNAME`
- `INTERNAL_API_KEY`
- `MINI_APP_PUBLIC_BASE_URL=https://<your-funnel-domain>/`
- `CORS_ORIGINS_RAW=https://<your-funnel-domain>`
- `REQUIRE_TELEGRAM_INIT_DATA=true`
- `ALLOW_INSECURE_DEV_AUTH=false`
- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL`:
  - `http://ollama:11434` if running `ollama` service in compose (`--profile ollama`)
  - `http://host.docker.internal:11434` if using host Ollama
- `VITE_BOT_USERNAME=<your_bot_username>`

2. Build and run production profile:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d

# Optional: start bundled Ollama service
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile ollama up -d

# Verify
curl http://localhost:8080/
curl http://localhost:8080/api/health
```

3. Publish via Tailscale Funnel (already configured in your setup):
- Example public URL: `https://macbook-pro.tailba5f18.ts.net/`
- Route funnel traffic to local `:8080`.

## Database Migrations
- Local manual run:
```bash
cd backend
alembic upgrade head
```

## Telegram Setup Checklist
1. Create bot via `@BotFather`, get token.
2. Set Mini App button in bot menu for `https://t.me/<BOT_USERNAME>/app`.
3. Ensure Mini App opens with deep links:
- `https://t.me/<BOT_USERNAME>/app?startapp=sc_natal`
- `https://t.me/<BOT_USERNAME>/app?startapp=sc_stories`
- `https://t.me/<BOT_USERNAME>/app?startapp=sc_tarot`
4. For secure operations, Mini App sends `X-Telegram-Init-Data` header.

## API Summary
- `POST /v1/natal/profile`
- `POST /v1/natal/calculate`
- `GET /v1/natal/latest`
- `GET /v1/natal/full`
- `GET /v1/forecast/daily`
- `GET /v1/forecast/stories`
- `POST /v1/tarot/draw`
- `GET /v1/tarot/{session_id}`

## Notes
- Astrology engine uses Swiss Ephemeris (`pyswisseph`) with fallback mode if ephemeris files are unavailable.
- Tarot deck data is stored in `backend/app/assets/tarot_deck.json`.
- External providers integrated:
  - Astrology API: `astrologyapi.com` (`/western_chart_data`) via `ASTROLOGY_PROVIDER=astrologyapi`
  - Tarot text API: `tarotapi.dev` via `TAROT_PROVIDER=tarotapi_dev`
  - Tarot card images: `metabismuth/tarot-json` cards CDN (`TAROT_IMAGE_BASE_URL`)
- API responses are auto-localized to Russian by default (`ENABLE_RESPONSE_LOCALIZATION=true`).
- If AI provider is unavailable, tarot returns fallback text and hides cards from response.
