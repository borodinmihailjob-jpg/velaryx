const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const DEV_AUTH_ALLOWED = import.meta.env.VITE_ALLOW_DEV_AUTH === 'true';

// Default request timeout (90s — long enough for LLM fallback paths)
const REQUEST_TIMEOUT_MS = 90_000;

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function readInitDataFromUrl() {
  try {
    const hash = window.location.hash.startsWith('#')
      ? window.location.hash.slice(1)
      : window.location.hash;
    const hashParams = new URLSearchParams(hash);
    const fromHash = hashParams.get('tgWebAppData');
    if (fromHash) return fromHash;
  } catch { /* ignore */ }

  try {
    const searchParams = new URLSearchParams(window.location.search);
    const fromSearch = searchParams.get('tgWebAppData');
    if (fromSearch) return fromSearch;
  } catch { /* ignore */ }

  return null;
}

export function getTelegramInitData() {
  const fromWebApp = window.Telegram?.WebApp?.initData;
  if (fromWebApp) return fromWebApp;
  return readInitDataFromUrl();
}

export function resolveTgUserId() {
  const fromTelegram = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  if (fromTelegram) return String(fromTelegram);
  return localStorage.getItem('dev_tg_user_id') || '999001';
}

function buildHeaders(options = {}) {
  const initData = getTelegramInitData();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
    return headers;
  }

  const isLocalHost =
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1';

  if (DEV_AUTH_ALLOWED || isLocalHost) {
    headers['X-TG-USER-ID'] = resolveTgUserId();
    return headers;
  }

  throw new Error('Откройте Mini App внутри Telegram (через ссылку t.me), чтобы пройти авторизацию.');
}

async function throwResponseError(response) {
  const payload = await response.json().catch(() => ({}));
  let detail = payload?.detail;
  if (Array.isArray(detail)) {
    detail = detail
      .map((item) => {
        const msg = item?.msg || item?.message;
        const loc = Array.isArray(item?.loc) ? item.loc.join('.') : '';
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean)
      .join('; ');
  } else if (typeof detail === 'object' && detail !== null) {
    detail = detail.message || JSON.stringify(detail);
  }
  throw new ApiError(detail || `Request failed: ${response.status}`, response.status, payload);
}

export async function apiRequest(path, options = {}) {
  const headers = buildHeaders(options);

  // Abort after REQUEST_TIMEOUT_MS to prevent indefinite loading states
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new ApiError('Запрос занял слишком долго. Попробуйте ещё раз.', 408, null);
    }
    throw new ApiError(String(err?.message || err || 'Network error'), 0, null);
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    await throwResponseError(response);
  }

  return response.json().catch(() => {
    throw new ApiError('Сервер вернул неверный ответ. Попробуйте позже.', response.status, null);
  });
}

/**
 * Poll a background task until it completes or times out.
 * @param {string} taskId - ARQ job ID returned by the server
 * @param {number} intervalMs - polling interval in ms (default 2000)
 * @param {number} timeoutMs - max total wait time in ms (default 120000)
 * @returns {Promise<object>} - the task result object when done
 */
export async function pollTask(taskId, intervalMs = 2000, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const data = await apiRequest(`/v1/tasks/${taskId}`);

    if (data.status === 'done') return data.result;
    if (data.status === 'failed') {
      throw new ApiError(data.error || 'Задача завершилась с ошибкой', 500, null);
    }
    // status === 'pending' — wait and retry
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new ApiError('Превышено время ожидания ответа от сервера', 408, null);
}

/**
 * Calculate all 6 numerology numbers and enqueue LLM interpretation.
 * @param {string} fullName - Full birth name (Cyrillic or Latin)
 * @param {string} birthDate - ISO date string "YYYY-MM-DD"
 * @returns {Promise<{numbers: object, status: string, task_id: string|null}>}
 */
export async function calculateNumerology(fullName, birthDate) {
  return apiRequest('/v1/numerology/calculate', {
    method: 'POST',
    body: JSON.stringify({
      full_name: fullName,
      birth_date: birthDate,
    }),
  });
}
