#!/bin/bash
#
# Скрипт для тестирования LLM fallback механизма
#
# Использование:
#   chmod +x test-llm-fallback.sh
#   ./test-llm-fallback.sh

set -e

API_URL="${API_URL:-http://localhost:8000}"
TG_USER_ID="${TG_USER_ID:-123456}"

echo "════════════════════════════════════════════════"
echo "🧪 Тестирование LLM Fallback Механизма"
echo "════════════════════════════════════════════════"
echo ""
echo "API URL: $API_URL"
echo "Test User ID: $TG_USER_ID"
echo ""

# Проверка что backend запущен
echo "→ Проверка доступности backend..."
if ! curl -s -f "$API_URL/health" > /dev/null; then
    echo "❌ Backend недоступен на $API_URL"
    echo "   Запустите: docker compose up"
    exit 1
fi
echo "✅ Backend доступен"
echo ""

# Тест 1: Natal chart (маленький LLM запрос)
echo "════════════════════════════════════════════════"
echo "📊 Тест 1: Natal Chart (проверка основного провайдера)"
echo "════════════════════════════════════════════════"
echo ""

NATAL_RESPONSE=$(curl -s "$API_URL/v1/natal/profile" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: $TG_USER_ID" \
  -d '{
    "birth_date": "1990-01-01",
    "birth_time": "12:00:00",
    "birth_place": "Moscow, Russia",
    "latitude": 55.7558,
    "longitude": 37.6173,
    "timezone": "Europe/Moscow"
  }')

if echo "$NATAL_RESPONSE" | grep -q '"id"'; then
    echo "✅ Natal profile создан"
    PROFILE_ID=$(echo "$NATAL_RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
    echo "   Profile ID: $PROFILE_ID"
else
    echo "❌ Ошибка создания profile:"
    echo "$NATAL_RESPONSE" | jq '.' 2>/dev/null || echo "$NATAL_RESPONSE"
    exit 1
fi
echo ""

# Рассчитать natal chart
echo "→ Расчет natal chart..."
CHART_RESPONSE=$(curl -s "$API_URL/v1/natal/calculate" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: $TG_USER_ID" \
  -d "{\"profile_id\":\"$PROFILE_ID\"}")

if echo "$CHART_RESPONSE" | grep -q '"sun_sign"'; then
    echo "✅ Chart рассчитан"
else
    echo "❌ Ошибка расчета chart:"
    echo "$CHART_RESPONSE" | jq '.' 2>/dev/null || echo "$CHART_RESPONSE"
fi
echo ""

# Тест 2: Tarot reading (большой LLM запрос)
echo "════════════════════════════════════════════════"
echo "🔮 Тест 2: Tarot Reading (проверка LLM генерации)"
echo "════════════════════════════════════════════════"
echo ""

echo "→ Запрос tarot reading..."
TAROT_RESPONSE=$(curl -s "$API_URL/v1/tarot/draw" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-TG-USER-ID: $TG_USER_ID" \
  -d '{
    "spread_type": "three_card",
    "question": "Тестовый вопрос для проверки LLM"
  }')

if echo "$TAROT_RESPONSE" | grep -q '"session_id"'; then
    echo "✅ Tarot session создана"

    SESSION_ID=$(echo "$TAROT_RESPONSE" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)
    echo "   Session ID: $SESSION_ID"

    # Проверить какой провайдер использовался
    LLM_PROVIDER=$(echo "$TAROT_RESPONSE" | grep -o '"llm_provider":"[^"]*' | cut -d'"' -f4)
    if [ -n "$LLM_PROVIDER" ]; then
        echo "   🤖 LLM Provider: $LLM_PROVIDER"

        # Разбор провайдера
        if echo "$LLM_PROVIDER" | grep -q "ollama"; then
            echo "   ✅ Используется локальная Ollama"
        elif echo "$LLM_PROVIDER" | grep -q "openrouter"; then
            echo "   ⚠️  Fallback на OpenRouter"
        elif echo "$LLM_PROVIDER" | grep -q "gemini"; then
            echo "   ⚠️  Fallback на Gemini"
        else
            echo "   ℹ️  Локальный fallback (без LLM)"
        fi
    fi

    # Проверить AI interpretation
    AI_INTERPRETATION=$(echo "$TAROT_RESPONSE" | grep -o '"ai_interpretation":"[^"]*' | cut -d'"' -f4)
    if [ -n "$AI_INTERPRETATION" ] && [ "$AI_INTERPRETATION" != "null" ]; then
        echo "   ✅ AI interpretation присутствует (${#AI_INTERPRETATION} символов)"
    else
        echo "   ⚠️  AI interpretation отсутствует (LLM unavailable)"
    fi
else
    echo "❌ Ошибка создания tarot session:"
    echo "$TAROT_RESPONSE" | jq '.' 2>/dev/null || echo "$TAROT_RESPONSE"
    exit 1
fi
echo ""

# Проверка логов backend
echo "════════════════════════════════════════════════"
echo "📋 Проверка логов backend (последние 20 строк с LLM)"
echo "════════════════════════════════════════════════"
echo ""

if command -v docker > /dev/null 2>&1; then
    echo "→ Логи LLM запросов:"
    docker compose logs --tail=100 api 2>/dev/null | grep -E "LLM (request|success|failed|fallback)" | tail -20 || echo "   (нет логов LLM)"
else
    echo "   (docker не установлен, пропускаем проверку логов)"
fi
echo ""

# Итоговая статистика
echo "════════════════════════════════════════════════"
echo "📊 Итоговая статистика"
echo "════════════════════════════════════════════════"
echo ""

if command -v docker > /dev/null 2>&1; then
    echo "→ Распределение провайдеров за последние 100 запросов:"
    docker compose logs --tail=100 api 2>/dev/null | \
      grep "LLM success" | \
      sed -E 's/.*provider=([^ ]+).*/\1/' | \
      sort | uniq -c | \
      awk '{printf "   %s: %d запросов\n", $2, $1}' || echo "   (нет данных)"
    echo ""
fi

echo "════════════════════════════════════════════════"
echo "✅ Тестирование завершено"
echo "════════════════════════════════════════════════"
echo ""
echo "Рекомендации:"
echo "  1. Проверьте что используется основной провайдер (ollama)"
echo "  2. Для теста fallback - остановите Ollama и запустите снова"
echo "  3. Мониторьте логи: docker compose logs -f api | grep LLM"
echo ""
