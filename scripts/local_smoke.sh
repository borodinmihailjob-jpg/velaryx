#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TG_USER_ID="${TG_USER_ID:-999001}"
INTERNAL_API_KEY="${INTERNAL_API_KEY:-}"
HTTP_TIMEOUT_SECONDS="${HTTP_TIMEOUT_SECONDS:-180}"
READINESS_TIMEOUT_SECONDS="${READINESS_TIMEOUT_SECONDS:-120}"
RETRY_COUNT="${RETRY_COUNT:-4}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-4}"
STRICT_LLM="${STRICT_LLM:-true}"
STRICT_LLM_NORMALIZED="$(printf '%s' "$STRICT_LLM" | tr '[:upper:]' '[:lower:]')"

BIRTH_DATE="${BIRTH_DATE:-1996-06-11}"
BIRTH_TIME="${BIRTH_TIME:-08:30:00}"
BIRTH_PLACE="${BIRTH_PLACE:-Moscow}"
BIRTH_LATITUDE="${BIRTH_LATITUDE:-55.7558}"
BIRTH_LONGITUDE="${BIRTH_LONGITUDE:-37.6173}"
BIRTH_TIMEZONE="${BIRTH_TIMEZONE:-Europe/Moscow}"
TAROT_QUESTION="${TAROT_QUESTION:-What should I focus on today?}"

log() {
  printf '[local-smoke] %s\n' "$*"
}

die() {
  printf '[local-smoke] ERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

need_cmd curl
need_cmd python3

CURL_COMMON=(--silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS")
AUTH_HEADERS=(-H "X-TG-USER-ID: $TG_USER_ID")
if [[ -n "$INTERNAL_API_KEY" ]]; then
  AUTH_HEADERS+=(-H "X-Internal-API-Key: $INTERNAL_API_KEY")
fi

request_raw() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local auth_mode="${4:-auth}"
  local url="${API_BASE_URL%/}${path}"
  local args=("${CURL_COMMON[@]}" -X "$method" -w $'\n%{http_code}')
  local response body status

  if [[ "$auth_mode" == "auth" ]]; then
    args+=("${AUTH_HEADERS[@]}")
  fi
  if [[ -n "$payload" ]]; then
    args+=(-H "Content-Type: application/json" -d "$payload")
  fi
  args+=("$url")

  response="$(curl "${args[@]}" 2>&1)" || return 1
  body="${response%$'\n'*}"
  status="${response##*$'\n'}"

  if [[ ! "$status" =~ ^2[0-9][0-9]$ ]]; then
    printf 'HTTP %s %s %s -> %s\n' "$status" "$method" "$path" "$body" >&2
    return 1
  fi
  printf '%s' "$body"
}

request_or_fail() {
  local output
  output="$(request_raw "$@")" || die "Request failed: $1 $2"
  printf '%s' "$output"
}

request_with_retry() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local auth_mode="${4:-auth}"
  local attempt output

  for attempt in $(seq 1 "$RETRY_COUNT"); do
    if output="$(request_raw "$method" "$path" "$payload" "$auth_mode")"; then
      printf '%s' "$output"
      return 0
    fi
    if [[ "$attempt" -lt "$RETRY_COUNT" ]]; then
      sleep "$RETRY_DELAY_SECONDS"
    fi
  done
  die "Request failed after retries: $method $path"
}

task_status_value() {
  local json_payload="$1"
  printf '%s' "$json_payload" | python3 -c 'import json,sys; print(str((json.load(sys.stdin) or {}).get("status") or ""))'
}

task_id_value() {
  local json_payload="$1"
  printf '%s' "$json_payload" | python3 -c 'import json,sys; print(str((json.load(sys.stdin) or {}).get("task_id") or ""))'
}

resolve_task_if_pending() {
  local json_payload="$1"
  local timeout_seconds="${2:-120}"
  local poll_interval_seconds="${3:-2}"
  local status task_id started now elapsed task_json

  status="$(task_status_value "$json_payload")" || die "Cannot parse async status"
  if [[ "$status" != "pending" ]]; then
    printf '%s' "$json_payload"
    return 0
  fi

  task_id="$(task_id_value "$json_payload")" || die "Cannot parse task_id"
  [[ -n "$task_id" ]] || die "Server returned pending without task_id"

  started="$(date +%s)"
  while true; do
    task_json="$(request_or_fail "GET" "/v1/tasks/${task_id}")"
    status="$(printf '%s' "$task_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d.get("status") or ""))')" \
      || die "Cannot parse task status"

    if [[ "$status" == "done" ]]; then
      printf '%s' "$task_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); import json as _j; print(_j.dumps(d.get("result"), ensure_ascii=False, separators=(",", ":")))' \
        || die "Cannot extract task result"
      return 0
    fi
    if [[ "$status" == "failed" ]]; then
      local error_text
      error_text="$(printf '%s' "$task_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d.get("error") or "task failed"))')" || error_text="task failed"
      die "Background task failed: ${error_text}"
    fi

    now="$(date +%s)"
    elapsed=$((now - started))
    if (( elapsed >= timeout_seconds )); then
      die "Background task did not complete within ${timeout_seconds}s (task_id=${task_id})"
    fi
    sleep "$poll_interval_seconds"
  done
}

wait_for_health() {
  local started now elapsed health_json
  started="$(date +%s)"
  while true; do
    if health_json="$(request_raw "GET" "/health" "" "noauth")"; then
      if printf '%s' "$health_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("ok") is True else 1)'; then
        log "API is ready"
        return 0
      fi
    fi

    now="$(date +%s)"
    elapsed=$((now - started))
    if (( elapsed >= READINESS_TIMEOUT_SECONDS )); then
      die "API did not become ready within ${READINESS_TIMEOUT_SECONDS}s"
    fi
    sleep 2
  done
}

log "Waiting for ${API_BASE_URL%/}/health ..."
wait_for_health

profile_payload="$(python3 - <<PY
import json
payload = {
    "birth_date": "${BIRTH_DATE}",
    "birth_time": "${BIRTH_TIME}",
    "birth_place": "${BIRTH_PLACE}",
    "latitude": float("${BIRTH_LATITUDE}"),
    "longitude": float("${BIRTH_LONGITUDE}"),
    "timezone": "${BIRTH_TIMEZONE}",
}
print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
PY
)"

log "Creating natal profile"
profile_json="$(request_or_fail "POST" "/v1/natal/profile" "$profile_payload")"
profile_id="$(printf '%s' "$profile_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')" || die "Cannot parse profile id"

log "Calculating natal chart"
calc_payload="$(python3 - <<PY
import json
print(json.dumps({"profile_id": "${profile_id}"}, separators=(",", ":")))
PY
)"
calculate_json="$(request_or_fail "POST" "/v1/natal/calculate" "$calc_payload")"
printf '%s' "$calculate_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("sun_sign"), "sun_sign missing"' \
  || die "Natal calculate response invalid"

log "Checking full natal output"
full_json="$(request_or_fail "GET" "/v1/natal/full")"
full_json="$(resolve_task_if_pending "$full_json" 180 2)"
sections_count="$(printf '%s' "$full_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("interpretation_sections") or []))')" \
  || die "Cannot parse interpretation sections"
[[ "$sections_count" -ge 1 ]] || die "No natal interpretation sections returned"

log "Checking daily forecast"
daily_json="$(request_or_fail "GET" "/v1/forecast/daily")"
printf '%s' "$daily_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); e=int(d.get("energy_score",0)); assert 0 < e <= 100, "energy_score out of range"' \
  || die "Daily forecast response invalid"

log "Checking stories endpoint"
stories_json="$(request_with_retry "GET" "/v1/forecast/stories")"
stories_json="$(resolve_task_if_pending "$stories_json" 180 2)"
stories_info="$(printf '%s' "$stories_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); slides=d.get("slides") or []; provider=str(d.get("llm_provider") or ""); print(f"{len(slides)}|{provider}")')" \
  || die "Stories response invalid"
stories_count="${stories_info%%|*}"
stories_provider="${stories_info##*|}"
[[ "$stories_count" -ge 3 ]] || die "Stories returned less than 3 slides"

log "Checking tarot draw endpoint"
tarot_payload="$(python3 - <<PY
import json
print(json.dumps({"spread_type": "three_card", "question": "${TAROT_QUESTION}"}, separators=(",", ":")))
PY
)"
tarot_json="$(request_with_retry "POST" "/v1/tarot/draw" "$tarot_payload")"
tarot_info="$(printf '%s' "$tarot_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); interp=str(d.get("ai_interpretation") or "").strip(); provider=str(d.get("llm_provider") or ""); print(f"{1 if interp else 0}|{provider}")')" \
  || die "Tarot response invalid"
tarot_has_text="${tarot_info%%|*}"
tarot_provider="${tarot_info##*|}"
[[ "$tarot_has_text" == "1" ]] || die "Tarot interpretation is empty"

if [[ "$STRICT_LLM_NORMALIZED" == "true" ]]; then
  [[ "$stories_provider" != "local:fallback" ]] || die "Stories LLM provider is fallback"
  [[ "$tarot_provider" != "local:fallback" ]] || die "Tarot LLM provider is fallback"
fi

log "OK"
log "profile_id=${profile_id}"
log "stories_llm_provider=${stories_provider:-none}"
log "tarot_llm_provider=${tarot_provider:-none}"
log "Smoke check passed"
