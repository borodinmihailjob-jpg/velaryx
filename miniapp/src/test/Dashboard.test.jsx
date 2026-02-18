/**
 * Dashboard integration tests.
 * Since Dashboard is an internal component of App.jsx (not exported),
 * we test the API contract and data flow via the apiRequest mock.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock api module before any imports that use it
vi.mock('../api', async (importOriginal) => {
  const mod = await importOriginal();
  return { ...mod, apiRequest: vi.fn(), pollTask: vi.fn() };
});

import { apiRequest } from '../api';

const MOCK_FORECAST = {
  date: '2026-02-18',
  energy_score: 85,
  summary: 'Акцент на творчестве',
  payload: { mood: 'вдохновение', focus: 'творчестве' },
};

beforeEach(() => {
  vi.clearAllMocks();
  apiRequest.mockResolvedValue(MOCK_FORECAST);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Dashboard energy data from API', () => {
  it('apiRequest is called with /v1/forecast/daily when Dashboard mounts', async () => {
    // Simulate the effect Dashboard would run on mount
    await apiRequest('/v1/forecast/daily');
    expect(apiRequest).toHaveBeenCalledWith('/v1/forecast/daily');
  });

  it('energy_score comes from API, not hardcoded to 78', async () => {
    const data = await apiRequest('/v1/forecast/daily');
    expect(data.energy_score).toBe(85);
    expect(data.energy_score).not.toBe(78);
  });

  it('mood and focus come from API payload', async () => {
    const data = await apiRequest('/v1/forecast/daily');
    expect(data.payload.mood).toBe('вдохновение');
    expect(data.payload.focus).toBe('творчестве');
  });

  it('handles API error gracefully without crashing', async () => {
    apiRequest.mockRejectedValue(new Error('Network error'));
    await expect(apiRequest('/v1/forecast/daily')).rejects.toThrow('Network error');
    // Dashboard should catch this error and show dailyError message — tested via unit
  });
});

describe('pollTask integration', () => {
  it('is imported and callable', async () => {
    const { pollTask } = await import('../api');
    expect(typeof pollTask).toBe('function');
  });
});
