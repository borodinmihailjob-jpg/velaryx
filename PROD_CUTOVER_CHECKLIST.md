# Production Cutover Checklist (Docker + Tailscale Funnel)

Domain: `https://macbook-pro.tailba5f18.ts.net/`

## 1. Fill production secrets

Edit `/.env.prod`:
- `BOT_TOKEN`
- `BOT_USERNAME`
- `INTERNAL_API_KEY`
- `POSTGRES_PASSWORD`
- `VITE_BOT_USERNAME` (same as `BOT_USERNAME` without `@`)

If you run Ollama in Docker profile, set:
- `OLLAMA_BASE_URL=http://ollama:11434`

If you run Ollama on host machine, keep:
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

## 2. Start production stack

Without bundled Ollama:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
```

With bundled Ollama:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile ollama up --build -d
```

## 3. Attach Funnel to miniapp port

`miniapp` is exposed on host port `8080`.

Set Funnel:
```bash
tailscale funnel --bg 8080
tailscale funnel status
```

Expected: funnel points to local `:8080` and serves `https://macbook-pro.tailba5f18.ts.net/`.

## 4. Smoke checks

Local checks:
```bash
curl -i http://localhost:8080/
curl -i http://localhost:8080/api/health
```

Public checks:
```bash
curl -i https://macbook-pro.tailba5f18.ts.net/
curl -i https://macbook-pro.tailba5f18.ts.net/api/health
```

## 5. Telegram cutover

1. Ensure bot starts with valid `BOT_TOKEN` and `BOT_USERNAME`.
2. Open bot and run `/start`, verify the button opens miniapp.
3. Verify auth in backend works only with Telegram `initData`:
   - no `X-TG-USER-ID` dev auth in production.
4. Check deep links:
   - `https://t.me/<BOT_USERNAME>/app?startapp=sc_natal`
   - `https://t.me/<BOT_USERNAME>/app?startapp=sc_stories`
   - `https://t.me/<BOT_USERNAME>/app?startapp=sc_tarot`

## 6. Post-cutover operations

Check service health:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail=150 api
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail=150 bot
```

Restart policy verification:
- Reboot host machine.
- Run `docker ps` and ensure all services are back (`restart: unless-stopped`).

## 7. Rollback command

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
```
