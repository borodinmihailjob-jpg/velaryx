# 🚀 Быстрый старт: Tailscale + Auto-Fallback

Настройка стабильного доступа к локальной Ollama через Tailscale Funnel с автоматическим fallback на облачные LLM.

## 📋 Что будет работать

```
Telegram Bot → FastAPI Backend → [Приоритет провайдеров]
                                   1. Ollama через Tailscale (бесплатно)
                                   2. OpenRouter free tier (бесплатно)
                                   3. Gemini (бесплатно, лимиты)
```

**Результат:**
- ✅ Mac online → используется ваш бесплатный Ollama
- ✅ Mac offline или tunnel down → автоматический переключение на OpenRouter
- ✅ OpenRouter недоступен → fallback на Gemini
- ✅ Пользователь не замечает разницы

---

## 🎯 Шаг 1: Установка Ollama Proxy (на Mac)

```bash
# 1. Создать директорию
mkdir -p ~/ollama-proxy
cd ~/ollama-proxy

# 2. Скопировать файлы из проекта
cp ~/Documents/astrobot/ollama-proxy/main.py .
cp ~/Documents/astrobot/ollama-proxy/requirements.txt .

# 3. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 4. Установить зависимости
pip install -r requirements.txt

# 5. Протестировать proxy
python main.py
```

Откройте http://localhost:8888/health - должен вернуть `{"status":"healthy"}`

**Остановите proxy (Ctrl+C) перед следующим шагом.**

---

## 🔐 Шаг 2: Установка Tailscale (на Mac)

```bash
# 1. Установить Tailscale
brew install tailscale

# 2. Запустить сервис
sudo brew services start tailscale

# 3. Авторизоваться (откроется браузер)
sudo tailscale up

# 4. Проверить статус
tailscale status
```

---

## 🌐 Шаг 3: Включение Tailscale Funnel

```bash
# 1. Запустить proxy снова
cd ~/ollama-proxy
source venv/bin/activate
python main.py &

# 2. Включить публичный доступ через Funnel
tailscale funnel 8888

# Вы получите URL типа:
# https://your-macbook.tail1234.ts.net

# 3. Сохранить этот URL - он понадобится для backend!
echo "Мой Tailscale URL:" > ~/ollama-proxy/tailscale-url.txt
tailscale funnel status | grep "https://" >> ~/ollama-proxy/tailscale-url.txt

# 4. Проверить что работает через интернет
curl https://your-macbook.tail1234.ts.net/health
```

**✅ Если вернулся `{"status":"healthy"}` - Funnel работает!**

---

## ⚙️ Шаг 4: Настройка автозапуска (на Mac)

```bash
# 1. Скопировать launchd plist
cp ~/Documents/astrobot/ollama-proxy/com.astrobot.ollama-proxy.plist \
   ~/Library/LaunchAgents/

# 2. Загрузить сервис
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# 3. Проверить что запустился
launchctl list | grep ollama-proxy

# 4. Проверить логи
tail -f ~/ollama-proxy/proxy.log
```

**Теперь proxy будет автоматически стартовать при загрузке Mac!**

---

## 🔧 Шаг 5: Настройка AstroBot Backend

Обновите `.env` в корне проекта:

```bash
# === LLM Configuration ===

# Включить auto-fallback
LLM_PROVIDER=auto

# Primary: Ollama через Tailscale Funnel
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=https://your-macbook.tail1234.ts.net  # ⬅️ ВАШ URL!
OLLAMA_TIMEOUT_SECONDS=10  # Быстрый timeout для fallback

# Backup #1: OpenRouter (бесплатные модели)
OPENROUTER_API_KEY=sk-or-v1-...  # ⬅️ Получить на https://openrouter.ai/keys
OPENROUTER_MODEL=deepseek/deepseek-r1-0528:free
OPENROUTER_TIMEOUT_SECONDS=30

# Backup #2: Gemini (опционально)
GEMINI_API_KEY=...  # ⬅️ Получить на https://makersuite.google.com/app/apikey
GEMINI_MODEL=gemini-2.0-flash
```

### Где взять API ключи (бесплатно):

**OpenRouter:**
1. Зарегистрироваться на https://openrouter.ai
2. Получить ключ: https://openrouter.ai/keys
3. Настроить privacy: https://openrouter.ai/settings/privacy
   - Включить: "Allow free models to use my data for training"

**Gemini (опционально):**
1. Перейти на https://makersuite.google.com/app/apikey
2. Создать API key
3. Бесплатный лимит: 15 requests/minute

---

## 🧪 Шаг 6: Тестирование

### Тест 1: Проверка Ollama

```bash
# Запустить backend
docker compose up --build

# В другом терминале: сделать запрос
curl http://localhost:8000/v1/tarot/draw -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: 123" \
  -d '{
    "spread_type": "three_card",
    "question": "Тестовый вопрос"
  }'
```

**Посмотрите логи backend:**
```bash
docker compose logs api | grep LLM
```

Должны увидеть:
```
LLM request | provider=auto (ollama→openrouter→gemini)
LLM success | provider=ollama | time=2.34s
```

### Тест 2: Проверка fallback

```bash
# Остановить Ollama proxy на Mac
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Сделать тот же запрос
curl http://localhost:8000/v1/tarot/draw -X POST ...

# Проверить логи
docker compose logs api | grep LLM
```

Должны увидеть:
```
LLM request | provider=auto (ollama→openrouter→gemini)
Ollama failed, trying OpenRouter fallback...
LLM success | provider=openrouter (fallback) | time=3.12s
```

**✅ Если видите "provider=openrouter (fallback)" - всё работает!**

```bash
# Запустить proxy снова
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
```

---

## 📊 Мониторинг

### Проверить статус всех сервисов:

```bash
# 1. Ollama proxy на Mac
curl http://localhost:8888/health

# 2. Ollama через Tailscale
curl https://your-macbook.tail1234.ts.net/health

# 3. Backend health
curl http://localhost:8000/health

# 4. Tailscale статус
tailscale status
tailscale funnel status
```

### Логи:

```bash
# Proxy логи (на Mac)
tail -f ~/ollama-proxy/proxy.log

# Backend логи
docker compose logs -f api | grep LLM

# Фильтр только fallback событий
docker compose logs -f api | grep "fallback"
```

---

## 🔧 Troubleshooting

### Ollama недоступна через Tailscale

```bash
# Проверить что proxy запущен
ps aux | grep "python.*main.py"

# Проверить что Funnel активен
tailscale funnel status

# Перезапустить funnel
tailscale funnel off
tailscale funnel 8888

# Проверить firewall (если macOS блокирует)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/local/bin/python3
```

### Backend не переключается на fallback

```bash
# Проверить .env
grep -E "(LLM_PROVIDER|OLLAMA_TIMEOUT|OPENROUTER_API_KEY)" .env

# Проверить что ключи настроены
echo $OPENROUTER_API_KEY  # Должен быть не пустым

# Перезапустить backend
docker compose restart api
```

### OpenRouter возвращает ошибку

```bash
# Проверить privacy settings
# https://openrouter.ai/settings/privacy
# Должно быть включено: "Allow free models"

# Проверить лимиты
curl https://openrouter.ai/api/v1/auth/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

---

## 📈 Статистика использования

После настройки вы можете отслеживать какой провайдер используется:

```bash
# Количество запросов к каждому провайдеру за последний час
docker compose logs api --since 1h | grep "LLM success" | \
  sed -E 's/.*provider=([^ ]+).*/\1/' | sort | uniq -c

# Пример вывода:
#  45 ollama              # 45 запросов через Mac
#   3 openrouter (fallback)  # 3 раза упал Mac
#   1 gemini (fallback)      # 1 раз упали оба
```

---

## ✅ Готово!

Теперь у вас:
- ✅ Стабильный доступ к Ollama через Tailscale
- ✅ Автоматический fallback на OpenRouter/Gemini
- ✅ Подробное логирование для debugging
- ✅ Автозапуск при загрузке Mac

**Следующие шаги:**
1. Задеплоить на Render с этими же настройками
2. Добавить мониторинг (опционально)
3. Настроить alerts при частых fallback (опционально)

Полная документация в [ollama-proxy/README.md](ollama-proxy/README.md)
