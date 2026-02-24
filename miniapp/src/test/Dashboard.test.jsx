import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../api', () => ({
  apiRequest: vi.fn(),
  askOracle: vi.fn(),
  fetchUserHistory: vi.fn(),
  fetchWalletSummary: vi.fn(),
  fetchDailyForecast: vi.fn(),
  fetchNatalFree: vi.fn(),
  fetchNatalPremium: vi.fn(),
  fetchTarotFree: vi.fn(),
  fetchTarotPremium: vi.fn(),
  fetchCompatFree: vi.fn(),
  fetchCompatPremium: vi.fn(),
  fetchHoroscope: vi.fn(),
  topUpWalletBalance: vi.fn(),
  persistUserLanguageCode: vi.fn((code) => code || 'ru'),
  resolveUserLanguageCode: vi.fn(() => 'ru'),
  pollTask: vi.fn(),
}));

import App from '../App';
import {
  apiRequest, fetchUserHistory, fetchWalletSummary, fetchDailyForecast,
} from '../api';

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('onboarding_complete', '1');

  apiRequest.mockImplementation((path) => {
    if (path === '/v1/users/me') return Promise.resolve({ language_code: 'ru' });
    if (path === '/v1/natal/profile/latest') return Promise.resolve({ id: 'profile-1' });
    if (path === '/v1/natal/latest') return Promise.resolve({});
    return Promise.resolve({});
  });

  fetchDailyForecast.mockResolvedValue({
    mood: 'Ясность',
    focus: 'Внимание',
    energy_score: 7,
    summary: 'День благоприятен для новых начинаний',
  });
  fetchWalletSummary.mockResolvedValue({ balance_stars: 12, recent_entries: [] });
  fetchUserHistory.mockResolvedValue({ reports: [] });

  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('App coordinator — navigation', () => {
  it('renders oracle hub with brand mark and bottom tabs after init', async () => {
    render(<App />);

    // Wait for init to complete (LoadingScreen disappears)
    await waitFor(() => {
      expect(screen.getByText('Velaryx')).toBeInTheDocument();
    });

    expect(screen.getByRole('tab', { name: 'Оракул' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Совместимость' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Профиль' })).toBeInTheDocument();
  });

  it('oracle tab shows service cards for Tarot, Natal, Horoscope, Numerology', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Velaryx')).toBeInTheDocument();
    });

    expect(screen.getByText('Таро')).toBeInTheDocument();
    expect(screen.getByText('Натальная карта')).toBeInTheDocument();
    expect(screen.getByText(/Гороскоп/)).toBeInTheDocument();
    expect(screen.getByText('Нумерология')).toBeInTheDocument();
  });

  it('switches to compatibility tab and shows type selector', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Совместимость' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: 'Совместимость' }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Совместимость' })).toBeInTheDocument();
    });

    // The 4-step flow should start on type selector with type buttons
    expect(screen.getByText('Пара')).toBeInTheDocument();
    expect(screen.getByText('Дружба')).toBeInTheDocument();
    expect(screen.getByText('Работа')).toBeInTheDocument();
  });

  it('switches to profile tab and shows edit button and Stars balance section', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Профиль' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: 'Профиль' }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Профиль' })).toBeInTheDocument();
    });

    expect(screen.getByText('Изменить')).toBeInTheDocument();
    // Wait for wallet to load
    expect(await screen.findByText('12 ⭐')).toBeInTheDocument();
    expect(fetchWalletSummary).toHaveBeenCalled();
  });

  it('tapping service card navigates to screen (Tarot)', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Таро')).toBeInTheDocument();
    });

    // Find the Tarot service card button and click it
    const tarotCard = screen.getByText('Таро').closest('button');
    expect(tarotCard).not.toBeNull();
    fireEvent.click(tarotCard);

    // TarotScreen should now be visible
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Таро' })).toBeInTheDocument();
    });

    expect(screen.getByText('Расклад карт')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Что меня ждёт/i)).toBeInTheDocument();
  });

  it('back button on screen returns to oracle hub', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Таро')).toBeInTheDocument();
    });

    const tarotCard = screen.getByText('Таро').closest('button');
    fireEvent.click(tarotCard);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Таро' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Назад' }));

    await waitFor(() => {
      expect(screen.getByText('Velaryx')).toBeInTheDocument();
    });
  });

  it('shows onboarding when no profile flag', async () => {
    localStorage.removeItem('onboarding_complete');

    render(<App />);

    // Should show onboarding immediately (no init loading block)
    await waitFor(() => {
      expect(screen.getByText('Первичная настройка')).toBeInTheDocument();
    });
  });
});

describe('Compatibility tab — 4-step flow', () => {
  it('proceeds from type selector to data form on Continue click', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Совместимость' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: 'Совместимость' }));

    await waitFor(() => {
      expect(screen.getByText('Продолжить')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Продолжить'));

    await waitFor(() => {
      expect(screen.getByText('Первый человек')).toBeInTheDocument();
      expect(screen.getByText('Второй человек')).toBeInTheDocument();
    });
  });
});
