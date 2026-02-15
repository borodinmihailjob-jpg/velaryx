const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function readInitDataFromUrl() {
  try {
    const hash = window.location.hash.startsWith('#')
      ? window.location.hash.slice(1)
      : window.location.hash;
    const hashParams = new URLSearchParams(hash);
    const fromHash = hashParams.get('tgWebAppData');
    if (fromHash) {
      return fromHash;
    }
  } catch {
    // ignore
  }

  try {
    const searchParams = new URLSearchParams(window.location.search);
    const fromSearch = searchParams.get('tgWebAppData');
    if (fromSearch) {
      return fromSearch;
    }
  } catch {
    // ignore
  }

  return null;
}

export function getTelegramInitData() {
  const fromWebApp = window.Telegram?.WebApp?.initData;
  if (fromWebApp) {
    return fromWebApp;
  }
  return readInitDataFromUrl();
}

export function resolveTgUserId() {
  const fromTelegram = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  if (fromTelegram) {
    return String(fromTelegram);
  }
  return localStorage.getItem('dev_tg_user_id') || '999001';
}

function buildHeaders(options = {}) {
  const initData = getTelegramInitData();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  } else {
    headers['X-TG-USER-ID'] = resolveTgUserId();
  }
  return headers;
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
  throw new Error(detail || `Request failed: ${response.status}`);
}

export async function apiRequest(path, options = {}) {
  const headers = buildHeaders(options);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    await throwResponseError(response);
  }

  return response.json();
}

export async function apiBinaryRequest(path, options = {}) {
  const headers = buildHeaders(options);
  if (headers['Content-Type']) {
    delete headers['Content-Type'];
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    await throwResponseError(response);
  }

  return response.blob();
}
