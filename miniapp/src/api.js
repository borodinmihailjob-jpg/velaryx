const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const DEV_AUTH_ALLOWED = import.meta.env.VITE_ALLOW_DEV_AUTH === 'true';
const USER_LANG_STORAGE_KEY = 'astrobot_user_language_code';
// Per-feature storage key prefix (v2). One slot per feature prevents cross-feature overwrites.
const PENDING_STARS_PAYMENT_KEY_PREFIX = 'astrobot_pending_payment_v2:';
const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || '';

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

function normalizeLanguageCode(raw) {
  const source = String(raw || '').trim().toLowerCase();
  if (!source) return 'ru';
  const first = source.split(',')[0].split(';')[0].trim().replace('_', '-');
  const base = first.split('-')[0];
  return /^[a-z]{2,3}$/.test(base) ? base : 'ru';
}

export function resolveUserLanguageCode() {
  const fromTelegram = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
  if (fromTelegram) return normalizeLanguageCode(fromTelegram);

  const fromStorage = localStorage.getItem(USER_LANG_STORAGE_KEY);
  if (fromStorage) return normalizeLanguageCode(fromStorage);

  return normalizeLanguageCode(window.navigator?.language);
}

export function persistUserLanguageCode(languageCode) {
  const normalized = normalizeLanguageCode(languageCode);
  try {
    localStorage.setItem(USER_LANG_STORAGE_KEY, normalized);
  } catch {
    // ignore storage errors
  }
  return normalized;
}

function buildHeaders(options = {}) {
  const initData = getTelegramInitData();
  const userLang = resolveUserLanguageCode();
  const headers = {
    'Content-Type': 'application/json',
    'X-User-Language': userLang,
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

function withQueryParam(path, key, value) {
  const sep = path.includes('?') ? '&' : '?';
  return `${path}${sep}${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`;
}

function isWalletInsufficientError(err) {
  // Prefer machine-readable code from backend (new format)
  const detail = err?.detail?.detail;
  if (detail?.code === 'insufficient_wallet_balance') return true;
  // Fallback: string match for backward compatibility
  return err?.status === 402 && String(err?.message || '').toLowerCase().includes('баланс');
}

function _pendingPaymentKey(feature) {
  return PENDING_STARS_PAYMENT_KEY_PREFIX + String(feature);
}

function readPendingStarsPayment(feature) {
  try {
    const raw = localStorage.getItem(_pendingPaymentKey(feature));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

function writePendingStarsPayment(feature, data) {
  try {
    localStorage.setItem(_pendingPaymentKey(feature), JSON.stringify(data));
  } catch {
    // ignore storage errors
  }
}

function clearPendingStarsPayment(feature) {
  try {
    localStorage.removeItem(_pendingPaymentKey(feature));
  } catch {
    // ignore storage errors
  }
}

function isRetriableInvoiceOpenStatus(status) {
  return status === 'paid' || status === 'pending';
}

function assertInvoiceOpenStatus(status, invoice) {
  if (isRetriableInvoiceOpenStatus(status)) return;
  if (status === 'cancelled') {
    throw new ApiError('Оплата отменена. Можно нажать кнопку ещё раз, чтобы продолжить по этому же счёту.', 402, invoice);
  }
  throw new ApiError(`Оплата не завершена (${status}).`, 402, invoice);
}

function openTelegramInvoice(invoiceLink) {
  const tg = window.Telegram?.WebApp;
  if (tg?.openInvoice) {
    return new Promise((resolve, reject) => {
      try {
        tg.openInvoice(invoiceLink, (status) => resolve(String(status || 'unknown')));
      } catch (err) {
        reject(new ApiError(String(err?.message || err || 'Не удалось открыть счёт'), 0, null));
      }
    });
  }

  if (tg?.openTelegramLink) {
    return Promise.resolve('fallback_send_to_chat');
  }

  if (tg?.openLink) {
    return Promise.resolve('fallback_send_to_chat');
  }

  if (tg) {
    // Old Telegram clients may not expose openInvoice/openTelegramLink.
    return Promise.resolve('fallback_send_to_chat');
  }

  // Some Telegram clients can pass tgWebAppData in URL but fail to inject the JS bridge.
  // In that case, use the bot-chat fallback flow.
  if (getTelegramInitData()) {
    return Promise.resolve('fallback_send_to_chat');
  }

  throw new ApiError(
    'Оплата Stars доступна только внутри Telegram Mini App.',
    400,
    null,
  );
}

async function createStarsInvoice(feature) {
  return apiRequest('/v1/payments/stars/invoice', {
    method: 'POST',
    body: JSON.stringify({ feature }),
  });
}

export async function fetchStarsCatalog() {
  return apiRequest('/v1/payments/stars/catalog');
}

export async function fetchWalletSummary() {
  return apiRequest('/v1/payments/wallet');
}

async function fetchStarsPaymentStatus(paymentId) {
  return apiRequest(`/v1/payments/stars/${encodeURIComponent(paymentId)}`);
}

async function sendStarsInvoiceToChat(paymentId) {
  return apiRequest(`/v1/payments/stars/${encodeURIComponent(paymentId)}/send-to-chat`, {
    method: 'POST',
  });
}

function openBotChatForPayment() {
  const username = String(BOT_USERNAME || '').trim().replace(/^@/, '');
  if (!username) return;
  const url = `https://t.me/${username}`;
  const tg = window.Telegram?.WebApp;
  try {
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url);
      return;
    }
    if (tg?.openLink) {
      tg.openLink(url);
      return;
    }
  } catch {
    // fallback below
  }
  window.location.href = url;
}

async function waitForStarsPaymentConfirmation(paymentId, timeoutMs = 180_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const data = await fetchStarsPaymentStatus(paymentId);
    if (data?.status === 'paid' || data?.status === 'consumed') return data;
    if (data?.status === 'failed' || data?.status === 'cancelled') {
      throw new ApiError('Оплата не была подтверждена.', 402, data);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new ApiError('Оплата прошла, но сервер ещё не получил подтверждение. Не оплачивайте повторно: попробуйте ещё раз через несколько секунд.', 409, null);
}

async function resumePendingStarsPayment(feature) {
  const pending = readPendingStarsPayment(feature);
  if (!pending) return null;

  const createdAt = Number(pending.created_at_ms || 0);
  if (createdAt > 0 && Date.now() - createdAt > 24 * 60 * 60 * 1000) {
    clearPendingStarsPayment(feature);
    return null;
  }

  let status;
  try {
    status = await fetchStarsPaymentStatus(pending.payment_id);
  } catch (err) {
    if (err?.status === 404) {
      clearPendingStarsPayment(feature);
      return null;
    }
    throw err;
  }

  if (status?.status === 'paid' || status?.status === 'consumed') {
    clearPendingStarsPayment(feature);
    return String(pending.payment_id);
  }
  if (status?.status === 'failed' || status?.status === 'cancelled') {
    clearPendingStarsPayment(feature);
    return null;
  }

  if (pending.invoice_link) {
    const invoiceStatus = await openTelegramInvoice(pending.invoice_link);
    if (invoiceStatus === 'fallback_send_to_chat') {
      await sendStarsInvoiceToChat(pending.payment_id);
      openBotChatForPayment();
      throw new ApiError(
        'Счёт отправлен в чат с ботом и чат открыт автоматически. Оплатите его там, затем вернитесь в Mini App и нажмите кнопку ещё раз.',
        409,
        pending,
      );
    }
    // 'failed' or unknown status means the invoice can no longer be paid — clear and start fresh
    if (!isRetriableInvoiceOpenStatus(invoiceStatus) && invoiceStatus !== 'cancelled') {
      clearPendingStarsPayment(feature);
      return null;
    }
    assertInvoiceOpenStatus(invoiceStatus, pending);
  }

  await waitForStarsPaymentConfirmation(pending.payment_id);
  clearPendingStarsPayment(feature);
  return String(pending.payment_id);
}

async function payStarsForFeature(feature) {
  const resumedPaymentId = await resumePendingStarsPayment(feature);
  if (resumedPaymentId) return resumedPaymentId;

  const invoice = await createStarsInvoice(feature);
  if (!invoice?.payment_id || !invoice?.invoice_link) {
    throw new ApiError('Сервер не смог создать счёт Stars.', 500, invoice);
  }

  writePendingStarsPayment(feature, {
    feature,
    payment_id: String(invoice.payment_id),
    invoice_link: String(invoice.invoice_link),
    created_at_ms: Date.now(),
  });

  const invoiceStatus = await openTelegramInvoice(invoice.invoice_link);
  if (invoiceStatus === 'fallback_send_to_chat') {
    await sendStarsInvoiceToChat(invoice.payment_id);
    openBotChatForPayment();
    throw new ApiError(
      'Счёт отправлен в чат с ботом и чат открыт автоматически. Оплатите его там, затем вернитесь в Mini App и нажмите кнопку ещё раз.',
      409,
      invoice,
    );
  }
  // 'failed' or unknown: clear this invoice so the next attempt creates a fresh one
  if (!isRetriableInvoiceOpenStatus(invoiceStatus) && invoiceStatus !== 'cancelled') {
    clearPendingStarsPayment(feature);
  }
  assertInvoiceOpenStatus(invoiceStatus, invoice);

  await waitForStarsPaymentConfirmation(invoice.payment_id);
  clearPendingStarsPayment(feature);
  return String(invoice.payment_id);
}

export async function topUpWalletBalance(feature) {
  return payStarsForFeature(feature);
}

/**
 * Request premium natal chart via OpenRouter Gemini. Polls until complete.
 * @returns {Promise<object>} - result with {type:"natal_premium", report:{...}, sun_sign, moon_sign, rising_sign}
 */
export async function fetchNatalPremium() {
  let data;
  try {
    data = await apiRequest(withQueryParam('/v1/natal/full/premium', 'use_wallet', 'true'));
  } catch (err) {
    if (!isWalletInsufficientError(err)) throw err;
    const paymentId = await payStarsForFeature('natal_premium');
    data = await apiRequest(withQueryParam('/v1/natal/full/premium', 'payment_id', paymentId));
  }
  if (data.status === 'pending') {
    return await pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}

/**
 * Request premium tarot reading via OpenRouter Gemini. Polls until complete.
 * @param {string} spreadType - e.g. 'three_card'
 * @param {string} question - user's question (may be empty)
 * @returns {Promise<object>} - result with {type:"tarot_premium", cards, report, question, ...}
 */
export async function fetchTarotPremium(spreadType = 'three_card', question = '') {
  let data;
  try {
    data = await apiRequest(withQueryParam('/v1/tarot/premium', 'use_wallet', 'true'), {
      method: 'POST',
      body: JSON.stringify({ spread_type: spreadType, question: question || null }),
    });
  } catch (err) {
    if (!isWalletInsufficientError(err)) throw err;
    const paymentId = await payStarsForFeature('tarot_premium');
    data = await apiRequest(withQueryParam('/v1/tarot/premium', 'payment_id', paymentId), {
      method: 'POST',
      body: JSON.stringify({ spread_type: spreadType, question: question || null }),
    });
  }
  if (data.status === 'pending') {
    return await pollTask(data.task_id, 2000, 180_000);
  }
  return data;
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

/**
 * Request premium numerology report via OpenRouter Gemini. Polls until complete.
 * @param {string} fullName - Full birth name (Cyrillic or Latin)
 * @param {string} birthDate - ISO date string "YYYY-MM-DD"
 * @returns {Promise<object>} - result with {type:"numerology_premium", numbers:{...}, report:{...10 keys...}}
 */
export async function fetchNumerologyPremium(fullName, birthDate) {
  let data;
  try {
    data = await apiRequest(withQueryParam('/v1/numerology/premium', 'use_wallet', 'true'), {
      method: 'POST',
      body: JSON.stringify({ full_name: fullName, birth_date: birthDate }),
    });
  } catch (err) {
    if (!isWalletInsufficientError(err)) throw err;
    const paymentId = await payStarsForFeature('numerology_premium');
    data = await apiRequest(withQueryParam('/v1/numerology/premium', 'payment_id', paymentId), {
      method: 'POST',
      body: JSON.stringify({ full_name: fullName, birth_date: birthDate }),
    });
  }
  if (data.status === 'pending') {
    return await pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}

/**
 * Fetch user's report history from Redis (last 14 days).
 * @returns {Promise<{reports: Array}>}
 */
export async function fetchUserHistory() {
  return apiRequest('/v1/users/me/history');
}

/**
 * Save user's MBTI archetype type.
 * @param {string} mbtiType - 4-letter MBTI code, e.g. "INTJ"
 * @returns {Promise<object>} - updated user object
 */
export async function saveUserMbtiType(mbtiType) {
  return apiRequest('/v1/users/me', {
    method: 'PATCH',
    body: JSON.stringify({ mbti_type: mbtiType }),
  });
}

// Oracle
export async function askOracle(question) {
  return apiRequest('/v1/tarot/draw', {
    method: 'POST',
    body: JSON.stringify({ spread_type: 'one_card', question }),
  });
}

/**
 * Fetch daily forecast (cached per day).
 * @returns {Promise<object>} - {mood, focus, energy_score, summary, lucky_hint, ...}
 */
export async function fetchDailyForecast() {
  return apiRequest('/v1/forecast/daily');
}

/**
 * Fetch story-format horoscope. Enqueues ARQ job, polls until complete.
 * @returns {Promise<object>} - {slides: [...]}
 */
export async function fetchHoroscope() {
  const data = await apiRequest('/v1/forecast/stories');
  if (data?.status === 'pending' && data?.task_id) {
    return pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}

/**
 * Free natal chart. Enqueues ARQ job, polls until complete.
 * @returns {Promise<object>} - {sun_sign, moon_sign, rising_sign, interpretation_sections: [...]}
 */
export async function fetchNatalFree() {
  const data = await apiRequest('/v1/natal/full');
  if (data?.status === 'pending' && data?.task_id) {
    return pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}

/**
 * Free 3-card tarot spread. Enqueues ARQ job, polls until complete.
 * @param {string} question - user's question (may be empty)
 * @returns {Promise<object>} - {cards: [...], ai_interpretation: string}
 */
export async function fetchTarotFree(question = '') {
  const data = await apiRequest('/v1/tarot/draw', {
    method: 'POST',
    body: JSON.stringify({ spread_type: 'three_card', question: question || null }),
  });
  if (data?.status === 'pending' && data?.task_id) {
    return pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}

/**
 * Free compatibility report. Polls until complete.
 * @param {object} payload - {compat_type, birth_date_1, birth_date_2, name_1?, name_2?}
 * @returns {Promise<object>} - {result: {compatibility_score, summary, strength, risk, advice}}
 */
export async function fetchCompatFree(payload) {
  const data = await apiRequest('/v1/compat/free', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (data?.status === 'pending' && data?.task_id) {
    return pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}

/**
 * Premium compatibility report via Stars payment. Polls until complete.
 * @param {object} payload - {compat_type, birth_date_1, birth_date_2, name_1?, name_2?}
 * @returns {Promise<object>} - {compatibility_score, summary, green_flags, red_flags, ...}
 */
export async function fetchCompatPremium(payload) {
  let data;
  try {
    data = await apiRequest(withQueryParam('/v1/compat/premium', 'use_wallet', 'true'), {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (!isWalletInsufficientError(err)) throw err;
    const paymentId = await payStarsForFeature('compat_premium');
    data = await apiRequest(withQueryParam('/v1/compat/premium', 'payment_id', paymentId), {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
  if (data?.status === 'pending' && data?.task_id) {
    return pollTask(data.task_id, 2000, 180_000);
  }
  return data;
}
