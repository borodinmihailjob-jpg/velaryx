# 🎯 Что осталось сделать (требуется ваше участие)

Я настроил всё что мог автоматически! Вот что осталось:

---

## ✅ Что уже готово

1. ✅ **~/ollama-proxy/** - структура создана
2. ✅ **Python зависимости** - установлены (fastapi, uvicorn, httpx)
3. ✅ **launchd plist** - скопирован в `~/Library/LaunchAgents/`
4. ✅ **.env** - обновлен с `LLM_PROVIDER=auto` и `OLLAMA_TIMEOUT_SECONDS=10`

---

## 📋 Осталось 3 шага (10-15 минут)

### Шаг 1: Установить и настроить Tailscale (5 минут)

```bash
# 1. Установить Tailscale
brew install tailscale

# 2. Запустить сервис
sudo brew services start tailscale

# 3. Авторизоваться (откроется браузер)
sudo tailscale up

# 4. Проверить что работает
tailscale status
```

**Готово!** Tailscale установлен.

---

### Шаг 2: Запустить proxy и включить Funnel (5 минут)

```bash
# 1. Запустить proxy вручную (для теста)
cd ~/ollama-proxy
~/ollama-proxy/venv/bin/python main.py &

# Вы должны увидеть:
# INFO: Started server process [12345]
# INFO: Waiting for application startup.
# INFO: Application startup complete.
# INFO: Uvicorn running on http://0.0.0.0:8888

# 2. Проверить что proxy работает
curl http://localhost:8888/health

# Должен вернуть:
# {"status":"healthy","ollama":"available"}

# 3. Включить Tailscale Funnel
tailscale funnel 8888

# Вы получите URL типа:
# Available within your tailnet:
#   https://your-macbook.tail1234.ts.net/
#
# Available on the internet:
#   https://your-macbook.tail1234.ts.net/

# 4. ВАЖНО: Скопируйте этот URL!
echo "Мой Tailscale URL:"
tailscale funnel status | grep "https://"

# 5. Проверить через интернет
curl https://your-macbook.tail1234.ts.net/health
```

**✅ Если вернул `{"status":"healthy"}` - Funnel работает!**

---

### Шаг 3: Загрузить launchd service (2 минуты)

```bash
# 1. Загрузить service (автозапуск при загрузке Mac)
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# 2. Проверить что запустился
launchctl list | grep ollama-proxy

# Должен вернуть:
# 12345  0  com.astrobot.ollama-proxy

# 3. Проверить логи
tail -f ~/ollama-proxy/proxy.log

# Должны увидеть:
# INFO: Started server process
# INFO: Application startup complete.
```

**✅ Proxy теперь будет автоматически запускаться!**

---

### Шаг 4: Обновить .env с Tailscale URL (1 минута)

Откройте `.env` и замените:

```bash
# Было:
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Стало (вставьте ваш URL из Шага 2):
OLLAMA_BASE_URL=https://your-macbook.tail1234.ts.net
```

**Или через командную строку:**

```bash
# Замените YOUR_URL на ваш реальный URL
sed -i '' 's|OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=https://YOUR_URL.ts.net|' .env
```

---

### Шаг 5: Протестировать (3 минуты)

```bash
# 1. Перезапустить backend
docker compose down
docker compose up --build -d

# 2. Запустить тест
./test-llm-fallback.sh

# 3. Проверить логи
docker compose logs api | grep LLM

# Должны увидеть:
# LLM request | provider=auto (ollama→openrouter→gemini)
# LLM success | provider=ollama | time=2.34s
```

**✅ Если видите "provider=ollama" - всё работает!**

---

## 🎁 Опционально: Получить API ключи для fallback

Если Ollama недоступна, backend автоматически переключится на:

### OpenRouter (бесплатные модели)

1. Регистрация: https://openrouter.ai
2. Получить ключ: https://openrouter.ai/keys
3. Настроить privacy: https://openrouter.ai/settings/privacy
   - ✅ Включить: "Allow free models to use my data for training"
4. Добавить в `.env`:
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

### Gemini (опционально)

1. Получить ключ: https://makersuite.google.com/app/apikey
2. Добавить в `.env`:
   ```bash
   GEMINI_API_KEY=...
   ```

---

## 🧪 Тест fallback механизма

### Тест 1: Ollama работает
```bash
docker compose logs api | grep "LLM success"
# Ожидаем: provider=ollama
```

### Тест 2: Ollama offline (fallback)
```bash
# Остановить proxy
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Сделать запрос
curl http://localhost:8000/v1/tarot/draw -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: 123" \
  -d '{"spread_type":"three_card","question":"test"}'

# Проверить логи
docker compose logs api | grep "LLM"

# Ожидаем:
# Ollama failed, trying OpenRouter fallback...
# LLM success | provider=openrouter (fallback)

# Запустить proxy снова
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
```

---

## 📚 Полезные команды

```bash
# === Статус сервисов ===
curl http://localhost:8888/health              # Proxy локально
curl https://YOUR_URL.ts.net/health            # Proxy через Tailscale
tailscale status                               # Tailscale статус
tailscale funnel status                        # Funnel статус
docker compose logs api | grep LLM             # Backend LLM логи

# === Управление proxy ===
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist  # Stop
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist    # Start
tail -f ~/ollama-proxy/proxy.log               # Логи

# === Тестирование ===
./test-llm-fallback.sh                         # Автотест
docker compose logs -f api | grep fallback     # Отследить fallback события
```

---

## 🎯 Краткий чеклист

- [ ] `brew install tailscale`
- [ ] `sudo tailscale up`
- [ ] `cd ~/ollama-proxy && ~/ollama-proxy/venv/bin/python main.py &`
- [ ] `tailscale funnel 8888`
- [ ] Скопировать URL из `tailscale funnel status`
- [ ] `launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist`
- [ ] Обновить `OLLAMA_BASE_URL` в `.env` на Tailscale URL
- [ ] `docker compose up --build`
- [ ] `./test-llm-fallback.sh`

---

## 📖 Документация

Если что-то не ясно:
- [TAILSCALE_SETUP.md](TAILSCALE_SETUP.md) - Детальная инструкция
- [ollama-proxy/README.md](ollama-proxy/README.md) - Документация proxy
- [ollama-proxy/COMMANDS.md](ollama-proxy/COMMANDS.md) - Шпаргалка команд

---

## 🆘 Если что-то не работает

### Proxy не запускается
```bash
# Проверить логи ошибок
cat ~/ollama-proxy/proxy.error.log

# Проверить что Python и пакеты установлены
~/ollama-proxy/venv/bin/python --version
~/ollama-proxy/venv/bin/pip list | grep fastapi
```

### Tailscale не авторизуется
```bash
# Попробовать снова
sudo tailscale down
sudo tailscale up

# Проверить статус
tailscale status
```

### Backend не подключается к Ollama
```bash
# Проверить что URL правильный
grep OLLAMA_BASE_URL .env

# Проверить что URL отвечает
curl $(grep OLLAMA_BASE_URL .env | cut -d= -f2)/health

# Перезапустить backend
docker compose restart api
```

---

**Готово!** После этих шагов у вас будет полностью рабочая система с auto-fallback 🚀
