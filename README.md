# AstroBot Monorepo

Telegram bot + Mini App for astrology, tarot, compatibility deep-links, and wishlist sharing.

## Stack
- `backend`: FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis
- `bot`: aiogram worker
- `miniapp`: React + Vite + Telegram Mini Apps SDK + Framer Motion
- Deploy target: Render (`render.yaml` included)

## Implemented Features
- Natal profile + natal calculation endpoints (`/v1/natal/*`)
- Daily forecast endpoint (`/v1/forecast/daily`)
- Tarot spreads endpoint (`/v1/tarot/*`)
- Compatibility invite/start flow with deep-links (`comp_*`)
- Wishlist public sharing + reservation flow (`wl_*`)
- Telegram Mini App `startapp` routing
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
- `VITE_BOT_USERNAME`
4. Keep production security flags:
- `REQUIRE_TELEGRAM_INIT_DATA=true`
- `ALLOW_INSECURE_DEV_AUTH=false`

## Telegram Setup Checklist
1. Create bot via `@BotFather`, get token.
2. Set Mini App button in bot menu for `https://t.me/<BOT_USERNAME>/app`.
3. Ensure Mini App opens with deep links:
- `https://t.me/<BOT_USERNAME>/app?startapp=comp_<token>`
- `https://t.me/<BOT_USERNAME>/app?startapp=wl_<token>`
4. For secure operations, Mini App sends `X-Telegram-Init-Data` header.

## API Summary
- `POST /v1/natal/profile`
- `POST /v1/natal/calculate`
- `GET /v1/natal/latest`
- `GET /v1/forecast/daily`
- `POST /v1/tarot/draw`
- `GET /v1/tarot/{session_id}`
- `POST /v1/compat/invites`
- `POST /v1/compat/start`
- `POST /v1/wishlists`
- `POST /v1/wishlists/{wishlist_id}/items`
- `GET /v1/public/wishlists/{public_token}`
- `POST /v1/public/wishlists/{public_token}/items/{item_id}/reserve`

## Notes
- Astrology engine uses Swiss Ephemeris (`pyswisseph`) with fallback mode if ephemeris files are unavailable.
- Tarot deck data is stored in `backend/app/assets/tarot_deck.json`.
