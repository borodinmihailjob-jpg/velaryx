# Ollama Proxy Setup

FastAPI proxy для безопасного доступа к локальной Ollama через Tailscale Funnel.

## Зачем нужен proxy?

- 🔒 Безопасный публичный доступ к Ollama через HTTPS
- 📊 Логирование всех запросов
- ❤️ Health checks для мониторинга
- 🔄 Автоматический перезапуск при сбоях

## Быстрая установка

### 1. Установить Tailscale на Mac

```bash
# Установка через Homebrew
brew install tailscale

# Запуск Tailscale
sudo brew services start tailscale

# Авторизация (откроется браузер)
sudo tailscale up

# Проверка статуса
tailscale status
```

### 2. Установить Ollama (если еще не установлена)

```bash
# Скачать с https://ollama.com или через brew
brew install ollama

# Запустить Ollama
ollama serve

# В другом терминале: установить модель
ollama pull qwen2.5:7b
```

### 3. Настроить Ollama Proxy

```bash
# Создать директорию
mkdir -p ~/ollama-proxy
cd ~/ollama-proxy

# Скопировать файлы из проекта
cp ~/Documents/astrobot/ollama-proxy/main.py .
cp ~/Documents/astrobot/ollama-proxy/requirements.txt .

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### 4. Протестировать proxy локально

```bash
# Запустить proxy (в новом терминале)
cd ~/ollama-proxy
source venv/bin/activate
python main.py

# Proxy запустится на http://localhost:8888

# В другом терминале: проверить health
curl http://localhost:8888/health

# Должен вернуть:
# {"status":"healthy","ollama":"available","version":"0.x.x"}
```

### 5. Настроить автозапуск через launchd

```bash
# Скопировать plist в LaunchAgents
cp ~/Documents/astrobot/ollama-proxy/com.astrobot.ollama-proxy.plist \
   ~/Library/LaunchAgents/

# Загрузить service
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Проверить что запустилось
launchctl list | grep ollama-proxy

# Проверить логи
tail -f ~/ollama-proxy/proxy.log
```

**Теперь proxy будет автоматически запускаться при загрузке Mac!**

### 6. Включить Tailscale Funnel

```bash
# Открыть порт 8888 для публичного доступа
tailscale funnel 8888

# Tailscale выдаст URL типа:
# https://your-macbook.tail1234.ts.net
```

**Скопируйте этот URL - он понадобится для настройки backend!**

### 7. Протестировать публичный доступ

```bash
# Получить ваш Tailscale URL
tailscale funnel status

# Проверить health check через интернет
curl https://your-macbook.tail1234.ts.net/health

# Должен вернуть то же самое что и локально
```

## Настройка AstroBot backend

Теперь обновите `.env` в проекте AstroBot:

```bash
# === LLM Configuration ===

# Primary: Ollama через Tailscale Funnel
OLLAMA_BASE_URL=https://your-macbook.tail1234.ts.net
OLLAMA_TIMEOUT_SECONDS=10  # Быстрый timeout для fallback

# Auto-fallback на облачные провайдеры
LLM_PROVIDER=auto

# Backup #1: OpenRouter (бесплатные модели)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=deepseek/deepseek-r1-0528:free

# Backup #2: Gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

## Управление сервисом

```bash
# Остановить proxy
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Запустить снова
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Перезапустить после изменений
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Посмотреть логи
tail -f ~/ollama-proxy/proxy.log

# Посмотреть ошибки
tail -f ~/ollama-proxy/proxy.error.log
```

## Отключить автозапуск

```bash
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
rm ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
```

## Проверка работы fallback

### Тест 1: Ollama работает

```bash
# Mac включен, Ollama работает
curl http://localhost:8000/v1/tarot/draw -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: 123" \
  -d '{"spread_type":"three_card","question":"test"}'

# В логах backend должно быть:
# "llm_provider": "ollama:qwen2.5:7b"
```

### Тест 2: Ollama недоступна (fallback)

```bash
# Остановить Ollama
pkill ollama

# Сделать тот же запрос
curl http://localhost:8000/v1/tarot/draw -X POST ...

# Backend должен автоматически переключиться на OpenRouter:
# "llm_provider": "openrouter:deepseek-r1"
```

## Мониторинг

### Health check endpoint

```bash
# Проверить статус Ollama
curl https://your-macbook.tail1234.ts.net/health

# Ответ при OK:
{
  "status": "healthy",
  "ollama": "available",
  "version": "0.5.4"
}

# Ответ при ошибке:
{
  "detail": "Ollama недоступен: Connection refused"
}
```

### Tailscale статус

```bash
# Посмотреть все активные подключения
tailscale status

# Проверить что funnel работает
tailscale funnel status
```

## Troubleshooting

### Proxy не запускается

```bash
# Проверить логи ошибок
cat ~/ollama-proxy/proxy.error.log

# Проверить что Python и зависимости на месте
~/ollama-proxy/venv/bin/python --version
~/ollama-proxy/venv/bin/pip list | grep fastapi
```

### Ollama недоступна

```bash
# Проверить что Ollama запущена
curl http://localhost:11434/api/version

# Если не отвечает - запустить
ollama serve

# Проверить модель
ollama list
```

### Tailscale Funnel не работает

```bash
# Проверить статус
tailscale status

# Перезапустить funnel
tailscale funnel off
tailscale funnel 8888
```

### Backend не подключается

```bash
# Проверить URL в .env
echo $OLLAMA_BASE_URL

# Проверить что URL отвечает
curl $OLLAMA_BASE_URL/health

# Проверить логи backend
docker compose logs api | grep -i ollama
```

## Безопасность

- ✅ Tailscale Funnel использует HTTPS автоматически
- ✅ Только авторизованные устройства в Tailscale сети
- ✅ ACL правила для ограничения доступа (опционально)
- ✅ Логирование всех запросов

### Настроить ACL (опционально)

В [Tailscale Admin Console](https://login.tailscale.com/admin/acls):

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["autogroup:members"],
      "dst": ["your-macbook:8888"]
    }
  ]
}
```

## Полезные ссылки

- [Ollama Documentation](https://ollama.com/docs)
- [Tailscale Funnel Guide](https://tailscale.com/kb/1223/funnel)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
