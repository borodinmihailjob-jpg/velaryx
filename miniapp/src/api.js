const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function getTelegramInitData() {
  return window.Telegram?.WebApp?.initData || null;
}

export function resolveTgUserId() {
  const fromTelegram = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  if (fromTelegram) {
    return String(fromTelegram);
  }
  return localStorage.getItem('dev_tg_user_id') || '999001';
}

export async function apiRequest(path, options = {}) {
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

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}
