# AstroBot Monorepo

Telegram bot + Mini App for astrology and tarot.

## Stack
- `backend`: FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis
- `bot`: aiogram worker
- `miniapp`: React + Vite + Telegram Mini Apps SDK + Framer Motion
- Deploy target: Render (`render.yaml` included)

## Implemented Features
- Natal profile + full natal map (`/v1/natal/*`)
- Daily forecast + stories mode (`/v1/forecast/*`)
- Tarot spreads endpoint (`/v1/tarot/*`)
- AI interpretation for tarot (OpenRouter/Gemini with fallback)
- Telegram Mini App `startapp` routing (`sc_*`)
- Telegram `initData` signature validation on backend

## Local Development
1. Copy env:
```bash
cp .env.example .env
```
2. Start:
```bash
docker compose up --build
```
3. API docs:
- http://localhost:8000/docs

## Database Migrations
- Local manual run:
```bash
cd backend
alembic upgrade head
```
- Render uses `preDeployCommand: alembic upgrade head` in `render.yaml`.

## Render Deployment
1. In Render dashboard choose **Blueprint** and connect this repo.
2. Render will create services from `render.yaml`:
- `astrobot-postgres` (managed Postgres)
- `astrobot-redis` (key-value)
- `astrobot-api` (FastAPI web)
- `astrobot-bot` (aiogram worker)
- `astrobot-miniapp` (static web)
3. Set required secret env vars in Render:
- `BOT_TOKEN`
- `BOT_USERNAME`
- `INTERNAL_API_KEY` (same value for `astrobot-api` and `astrobot-bot`)
- `MINI_APP_PUBLIC_BASE_URL`
- `CORS_ORIGINS_RAW` (include miniapp public URL)
- `VITE_API_BASE_URL` (public URL of `astrobot-api`)
- `VITE_ALLOW_DEV_AUTH=false` (production miniapp should use Telegram initData only)
- `VITE_TAROT_LOADING_GIF` (optional URL/path for tarot loading GIF, e.g. `/tarot-loader.gif`)
- `VITE_BOT_USERNAME`
- Optional external engines:
- `ASTROLOGY_PROVIDER=astrologyapi` + `ASTROLOGYAPI_USER_ID` + `ASTROLOGYAPI_API_KEY`
- `TAROT_PROVIDER=tarotapi_dev`
- Optional LLM for tarot explanations:
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default `gemini-2.0-flash`)
- OpenRouter alternative:
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENROUTER_FALLBACK_MODELS_RAW` (comma-separated models)
- `LLM_PROVIDER` (`openrouter`, `gemini`, `auto`)
- For OpenRouter free models, set privacy policy in dashboard to allow free-model routing:
- `https://openrouter.ai/settings/privacy`
4. Keep production security flags:
- `REQUIRE_TELEGRAM_INIT_DATA=true`
- `ALLOW_INSECURE_DEV_AUTH=false`

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
