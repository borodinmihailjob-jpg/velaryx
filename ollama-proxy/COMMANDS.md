# 📖 Шпаргалка команд Ollama Proxy + Tailscale

Быстрая справка по управлению Ollama proxy и Tailscale.

---

## 🚀 Управление Ollama Proxy

### Запуск/остановка вручную

```bash
# Запустить proxy вручную (для тестирования)
cd ~/ollama-proxy
source venv/bin/activate
python main.py

# Остановить: Ctrl+C
```

### Управление через launchd (автозапуск)

```bash
# Запустить service
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Остановить service
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Перезапустить service
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# Проверить статус
launchctl list | grep ollama-proxy
```

### Логи

```bash
# Смотреть логи в реальном времени
tail -f ~/ollama-proxy/proxy.log

# Смотреть ошибки
tail -f ~/ollama-proxy/proxy.error.log

# Последние 50 строк
tail -50 ~/ollama-proxy/proxy.log

# Поиск по логам
grep "error" ~/ollama-proxy/proxy.error.log
grep "Chat completion" ~/ollama-proxy/proxy.log
```

---

## 🌐 Управление Tailscale

### Основные команды

```bash
# Статус Tailscale
tailscale status

# Показать свой Tailscale IP
tailscale ip

# Проверить что funnel работает
tailscale funnel status

# Включить funnel на порту 8888
tailscale funnel 8888

# Выключить funnel
tailscale funnel off

# Перезапустить funnel
tailscale funnel off
tailscale funnel 8888
```

### Статус и мониторинг

```bash
# Показать все устройства в сети
tailscale status

# Показать детальный статус
tailscale status --json | jq '.'

# Проверить версию
tailscale version

# Показать текущий домен
tailscale status | grep "$(hostname)" | awk '{print $1}'
```

### Переподключение

```bash
# Отключиться
tailscale down

# Подключиться снова
tailscale up

# Выйти из сети (logout)
tailscale logout

# Войти заново
sudo tailscale up
```

---

## 🧪 Тестирование

### Health checks

```bash
# Локальный proxy
curl http://localhost:8888/health

# Через Tailscale (замените URL на ваш)
curl https://your-macbook.tail1234.ts.net/health

# С выводом всех деталей
curl -v http://localhost:8888/health
```

### Тест LLM запроса

```bash
# Через локальный proxy
curl http://localhost:8888/v1/chat/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:7b",
    "messages": [{"role": "user", "content": "Привет!"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'

# Через Tailscale
curl https://your-macbook.tail1234.ts.net/v1/chat/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:7b",
    "messages": [{"role": "user", "content": "Привет!"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### Тест из AstroBot backend

```bash
# Из директории проекта
cd ~/Documents/astrobot

# Запустить тестовый скрипт
./test-llm-fallback.sh

# С кастомными параметрами
API_URL=http://localhost:8000 TG_USER_ID=999 ./test-llm-fallback.sh
```

---

## 🔍 Диагностика

### Проверка что Ollama работает

```bash
# Проверить что Ollama запущена
curl http://localhost:11434/api/version

# Список установленных моделей
ollama list

# Запустить Ollama (если не запущена)
ollama serve
```

### Проверка портов

```bash
# Проверить что proxy слушает на 8888
lsof -i :8888

# Проверить что Ollama слушает на 11434
lsof -i :11434

# Показать все открытые порты
netstat -an | grep LISTEN
```

### Сетевая диагностика

```bash
# Проверить доступность proxy с другого устройства
# (замените IP на ваш локальный IP Mac)
curl http://192.168.1.100:8888/health

# Проверить DNS для Tailscale домена
nslookup your-macbook.tail1234.ts.net

# Трассировка до Tailscale endpoint
traceroute your-macbook.tail1234.ts.net
```

---

## 📊 Мониторинг логов AstroBot

### Все LLM события

```bash
# Смотреть LLM логи в реальном времени
docker compose logs -f api | grep LLM

# Только успешные запросы
docker compose logs api | grep "LLM success"

# Только fallback события
docker compose logs api | grep "fallback"

# Только ошибки
docker compose logs api | grep "LLM FAILED"
```

### Статистика провайдеров

```bash
# За последние 100 запросов
docker compose logs --tail=100 api | \
  grep "LLM success" | \
  sed -E 's/.*provider=([^ ]+).*/\1/' | \
  sort | uniq -c

# За последний час
docker compose logs --since 1h api | \
  grep "LLM success" | \
  sed -E 's/.*provider=([^ ]+).*/\1/' | \
  sort | uniq -c

# С временными метками
docker compose logs --since 1h api | \
  grep "LLM success" | \
  awk '{print $1, $2, $NF}'
```

---

## 🛠 Обслуживание

### Обновление proxy кода

```bash
# 1. Остановить service
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# 2. Обновить код
cd ~/ollama-proxy
cp ~/Documents/astrobot/ollama-proxy/main.py .

# 3. Запустить снова
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# 4. Проверить что работает
curl http://localhost:8888/health
```

### Обновление зависимостей

```bash
cd ~/ollama-proxy
source venv/bin/activate
pip install --upgrade fastapi uvicorn httpx
pip freeze > requirements.txt
```

### Очистка логов

```bash
# Очистить старые логи
> ~/ollama-proxy/proxy.log
> ~/ollama-proxy/proxy.error.log

# Ротация логов (оставить последние 1000 строк)
tail -1000 ~/ollama-proxy/proxy.log > ~/ollama-proxy/proxy.log.tmp
mv ~/ollama-proxy/proxy.log.tmp ~/ollama-proxy/proxy.log
```

---

## 🚨 Быстрое решение проблем

### Proxy не отвечает

```bash
# 1. Проверить что запущен
ps aux | grep "python.*main.py"

# 2. Проверить логи ошибок
tail -20 ~/ollama-proxy/proxy.error.log

# 3. Перезапустить
launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist
launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist

# 4. Проверить
curl http://localhost:8888/health
```

### Tailscale Funnel не работает

```bash
# 1. Проверить статус
tailscale funnel status

# 2. Перезапустить funnel
tailscale funnel off
sleep 2
tailscale funnel 8888

# 3. Проверить firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --listapps | grep python

# 4. Добавить python в исключения
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add \
  ~/ollama-proxy/venv/bin/python
```

### Ollama не запускается

```bash
# 1. Убить старые процессы
pkill ollama

# 2. Запустить заново
ollama serve

# 3. Проверить в другом терминале
ollama list
```

### Backend не подключается

```bash
# 1. Проверить .env
grep OLLAMA_BASE_URL .env

# 2. Проверить что URL доступен
curl $(grep OLLAMA_BASE_URL .env | cut -d= -f2)/health

# 3. Перезапустить backend
docker compose restart api

# 4. Проверить логи
docker compose logs api | grep -E "(OLLAMA|LLM)" | tail -20
```

---

## 💡 Полезные alias для .zshrc

Добавьте в `~/.zshrc` для быстрого доступа:

```bash
# Ollama Proxy
alias proxy-start='launchctl load ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist'
alias proxy-stop='launchctl unload ~/Library/LaunchAgents/com.astrobot.ollama-proxy.plist'
alias proxy-restart='proxy-stop && proxy-start'
alias proxy-logs='tail -f ~/ollama-proxy/proxy.log'
alias proxy-errors='tail -f ~/ollama-proxy/proxy.error.log'
alias proxy-health='curl -s http://localhost:8888/health | jq'

# Tailscale
alias ts-status='tailscale status'
alias ts-funnel='tailscale funnel status'
alias ts-url='tailscale funnel status | grep "https://"'

# AstroBot
alias astro-logs='docker compose logs -f api | grep LLM'
alias astro-test='~/Documents/astrobot/test-llm-fallback.sh'
alias astro-stats='docker compose logs --tail=100 api | grep "LLM success" | sed -E "s/.*provider=([^ ]+).*/\1/" | sort | uniq -c'

# Применить changes:
# source ~/.zshrc
```

После добавления:
```bash
source ~/.zshrc

# Теперь можно использовать:
proxy-health
ts-url
astro-logs
```

---

## 📚 Дополнительные ресурсы

- [Ollama Documentation](https://ollama.com/docs)
- [Tailscale Funnel Guide](https://tailscale.com/kb/1223/funnel)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [OpenRouter API Docs](https://openrouter.ai/docs)

---

**Нужна помощь?** Посмотрите [README.md](README.md) или [TAILSCALE_SETUP.md](../TAILSCALE_SETUP.md)
