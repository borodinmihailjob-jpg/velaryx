import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiRequest, pollTask, ApiError } from '../api';

// Ensure dev auth is enabled so tests don't throw auth errors
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_BASE_URL: '',
    VITE_ALLOW_DEV_AUTH: 'true',
  },
  writable: true,
});

// Mock window.Telegram and localStorage for dev auth fallback
beforeEach(() => {
  Object.defineProperty(window, 'Telegram', { value: undefined, writable: true });
  Object.defineProperty(window, 'location', {
    value: { hostname: 'localhost', hash: '', search: '' },
    writable: true,
  });
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetch(body, { status = 200, ok = true } = {}) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  });
}

describe('apiRequest', () => {
  it('returns parsed JSON on success', async () => {
    mockFetch({ sun_sign: 'Aries' });
    const result = await apiRequest('/v1/natal/latest');
    expect(result).toEqual({ sun_sign: 'Aries' });
  });

  it('throws ApiError with status on non-OK response', async () => {
    mockFetch({ detail: 'Not found' }, { status: 404, ok: false });
    await expect(apiRequest('/v1/natal/latest')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
    });
  });

  it('throws ApiError on non-JSON response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.reject(new SyntaxError('bad json')),
    });
    await expect(apiRequest('/v1/natal/latest')).rejects.toMatchObject({
      name: 'ApiError',
    });
  });

  it('throws ApiError on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(apiRequest('/v1/natal/latest')).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
    });
  });

  it('uses X-TG-USER-ID header in dev mode', async () => {
    mockFetch({});
    await apiRequest('/v1/health');
    const [, opts] = global.fetch.mock.calls[0];
    expect(opts.headers['X-TG-USER-ID']).toBeDefined();
  });
});

describe('pollTask', () => {
  it('resolves immediately when task is done on first poll', async () => {
    mockFetch({ status: 'done', result: { sun_sign: 'Leo' } });
    const result = await pollTask('task-abc');
    expect(result).toEqual({ sun_sign: 'Leo' });
  });

  it('polls until done', async () => {
    let call = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      call += 1;
      const body = call < 3
        ? { status: 'pending' }
        : { status: 'done', result: { ok: true } };
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    });
    const result = await pollTask('task-xyz', 10, 5000);
    expect(result).toEqual({ ok: true });
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });

  it('throws ApiError when task fails', async () => {
    mockFetch({ status: 'failed', error: 'LLM timeout' });
    await expect(pollTask('task-fail', 10, 5000)).rejects.toMatchObject({
      name: 'ApiError',
    });
  });

  it('throws ApiError on timeout', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'pending' }),
    });
    await expect(pollTask('task-slow', 10, 50)).rejects.toMatchObject({
      status: 408,
    });
  });
});
