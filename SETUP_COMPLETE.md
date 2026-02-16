# ✅ AstroBot: Tailscale + Auto-Fallback Setup Complete

**Дата настройки:** 2026-02-16
**Статус:** 🎉 Полностью настроено и работает!

---

## 🎯 Что было настроено

### 1. **Ollama Proxy** (`~/ollama-proxy/`)
- ✅ FastAPI proxy сервер с health checks
- ✅ Автозапуск через launchd (PID: 47045)
- ✅ Логи: `~/ollama-proxy/proxy.log`
- ✅ Порт: 8888

### 2. **Tailscale Funnel**
- ✅ Публичный HTTPS endpoint
- ✅ URL: **https://macbook-pro.tailba5f18.ts.net**
- ✅ Доступен из любой точки мира
- ✅ Автоматический SSL сертификат

### 3. **Backend Auto-Fallback**
- ✅ Primary: Ollama через Tailscale
- ✅ Fallback #1: OpenRouter (бесплатные модели)
- ✅ Fallback #2: Gemini
- ✅ Timeout: 60 секунд
- ✅ Подробное логирование fallback событий

### 4. **Текущая конфигурация (.env)**
```bash
LLM_PROVIDER=auto
OLLAMA_BASE_URL=https://macbook-pro.tailba5f18.ts.net
OLLAMA_TIMEOUT_SECONDS=60
OLLAMA_MODEL=qwen2.5:7b
```

---

## 📊 Проверка работы

```bash
# 1. Proxy локально
curl http://localhost:8888/health
# → {"status":"healthy","ollama":"available","version":"0.16.1"}

# 2. Proxy через интернет
curl https://macbook-pro.tailba5f18.ts.net/health
# → {"status":"healthy","ollama":"available","version":"0.16.1"}

# 3. Backend API
curl http://localhost:8000/health
# → {"ok": true, "timestamp": "..."}

# 4. LLM тест (должен вернуть AI interpretation)
curl http://localhost:8000/v1/tarot/draw -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: 123" \
  -d '{"spread_type":"three_card","question":"Тест"}'
# → "llm_provider": "ollama:qwen2.5:7b"
```

---

## 🚀 Архитектура

```
┌─────────────────┐
│  Telegram Bot   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Backend API    │  LLM_PROVIDER=auto
│  (Docker)       │
└────────┬────────┘
         │
         ├─ PRIMARY ────────────┐
         │                      │
         ▼                      ▼
┌──────────────────┐   ┌───────────────────┐
│ Tailscale Funnel │   │  Mac (Ollama)     │
│ HTTPS            │──▶│  qwen2.5:7b       │
└──────────────────┘   └───────────────────┘
         │
         │ (если Mac offline)
         │
         ├─ FALLBACK #1 ───────▶ OpenRouter (бесплатно)
         │
         └─ FALLBACK #2 ───────▶ Gemini
```

---

## 📝 Полезные команды

### Управление Ollama Proxy
```bash
# Статус
launchctl list | grep ollama-proxy

# Логи (реальное время)
tail -f ~/ollama-proxy/proxy.log

# Ошибки
tail -f ~/ollama-proxy/proxy.error.log

# Остановить
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Запустить
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
```

### Tailscale Funnel
```bash
# Статус
tailscale funnel status

# Ваш публичный URL
tailscale funnel status | grep https://

# Проверить доступность
curl https://macbook-pro.tailba5f18.ts.net/health
```

### Backend
```bash
# Логи LLM запросов
docker compose logs -f api | grep LLM

# Только fallback события
docker compose logs -f api | grep fallback

# Статистика провайдеров (последние 100 запросов)
docker compose logs --tail=100 api | \
  grep "LLM success" | \
  sed -E 's/.*provider=([^ ]+).*/\1/' | \
  sort | uniq -c

# Перезапуск
docker compose restart api
```

### Тестирование
```bash
# Полный тест системы
./test-llm-fallback.sh

# Быстрый тест
curl http://localhost:8000/v1/tarot/draw -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: 123" \
  -d '{"spread_type":"three_card","question":"Тест"}'
```

---

## 🔧 Troubleshooting

### Proxy не работает
```bash
# 1. Проверить что запущен
ps aux | grep "python.*main.py"

# 2. Проверить логи
tail -20 ~/ollama-proxy/proxy.error.log

# 3. Перезапустить
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
```

### Tailscale Funnel недоступен
```bash
# 1. Проверить статус Tailscale
tailscale status

# 2. Проверить Funnel
tailscale funnel status

# 3. Перезапустить Funnel
tailscale funnel off
tailscale funnel 8888
```

### Backend использует fallback вместо Ollama
```bash
# 1. Проверить .env
grep OLLAMA_BASE_URL .env
grep OLLAMA_TIMEOUT .env

# 2. Проверить что URL доступен
curl https://macbook-pro.tailba5f18.ts.net/health

# 3. Проверить логи
docker compose logs api --tail=50 | grep -E "(LLM|Ollama)"

# 4. Перезапустить полностью
docker compose down && docker compose up -d
```

### Ollama медленно отвечает
```bash
# 1. Прогреть модель
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "Привет",
  "stream": false
}'

# 2. Увеличить timeout в .env
OLLAMA_TIMEOUT_SECONDS=90

# 3. Перезапустить backend
docker compose restart api
```

---

## 🎁 Опционально: Добавить fallback провайдеры

Для максимальной надежности добавьте API ключи облачных провайдеров:

### OpenRouter (бесплатные модели)
1. Регистрация: https://openrouter.ai
2. API Key: https://openrouter.ai/keys
3. Privacy Settings: https://openrouter.ai/settings/privacy
   - ✅ Включить: "Allow free models to use my data for training"
4. Добавить в `.env`:
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

### Gemini (Google AI)
1. API Key: https://makersuite.google.com/app/apikey
2. Лимиты: 15 requests/minute (бесплатно)
3. Добавить в `.env`:
   ```bash
   GEMINI_API_KEY=...
   ```

После добавления ключей:
```bash
docker compose restart api
```

---

## 📚 Документация

- [NEXT_STEPS.md](NEXT_STEPS.md) - Оригинальная инструкция
- [TAILSCALE_SETUP.md](TAILSCALE_SETUP.md) - Детальная настройка
- [ollama-proxy/README.md](ollama-proxy/README.md) - Документация proxy
- [ollama-proxy/COMMANDS.md](ollama-proxy/COMMANDS.md) - Шпаргалка команд
- [test-llm-fallback.sh](test-llm-fallback.sh) - Тестовый скрипт

---

## ✅ Checklist завершенной настройки

- [x] Ollama установлена и работает
- [x] Модель qwen2.5:7b загружена
- [x] Ollama Proxy создан и настроен
- [x] Python зависимости установлены
- [x] launchd service настроен
- [x] Tailscale установлен
- [x] Tailscale Funnel включен
- [x] Публичный URL получен
- [x] .env обновлен с Tailscale URL
- [x] Backend настроен на auto-fallback
- [x] Timeout увеличен до 60 секунд
- [x] Система протестирована
- [x] LLM работает через Tailscale

---

## 🎯 Что дальше?

1. **Опционально:** Добавить API ключи для OpenRouter/Gemini (см. выше)
2. **Мониторинг:** Периодически проверять логи `docker compose logs api | grep LLM`
3. **Статистика:** Отслеживать сколько запросов идет через Ollama vs fallback
4. **Deploy на Render:** Когда готов - задеплоить с этими же настройками

---

## 💡 Полезные алиасы для ~/.zshrc

Добавьте в `~/.zshrc` для быстрого доступа:

```bash
# Ollama Proxy
alias proxy-logs='tail -f ~/ollama-proxy/proxy.log'
alias proxy-health='curl -s http://localhost:8888/health | jq'
alias proxy-restart='launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist && launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist'

# Tailscale
alias ts-status='tailscale status'
alias ts-url='tailscale funnel status | grep https://'

# AstroBot
alias astro-logs='docker compose logs -f api | grep LLM'
alias astro-test='./test-llm-fallback.sh'
alias astro-stats='docker compose logs --tail=100 api | grep "LLM success" | sed -E "s/.*provider=([^ ]+).*/\1/" | sort | uniq -c'

# После добавления:
source ~/.zshrc
```

---

**🎉 Настройка завершена! Всё работает!**

Ваша LLM теперь доступна из любой точки мира через HTTPS с автоматическим fallback на облачные провайдеры. ✨
