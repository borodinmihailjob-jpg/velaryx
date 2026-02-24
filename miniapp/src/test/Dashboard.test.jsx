import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../api', () => ({
  apiRequest: vi.fn(),
  askOracle: vi.fn(),
  fetchUserHistory: vi.fn(),
  fetchWalletSummary: vi.fn(),
  persistUserLanguageCode: vi.fn((code) => code || 'ru'),
  resolveUserLanguageCode: vi.fn(() => 'ru'),
}));

import App from '../App';
import { apiRequest, askOracle, fetchUserHistory, fetchWalletSummary } from '../api';

function mockOracleResponse() {
  return {
    cards: [
      {
        position: 1,
        card_name: 'Шут',
        meaning: 'Начало нового пути',
        is_reversed: false,
        slot_label: 'Знак',
      },
    ],
    ai_interpretation: 'Суть: Начинай с любопытства. Сделай: Выбери первый шаг сегодня. Избегай: Страха ошибки.',
  };
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('onboarding_complete', '1');

  apiRequest.mockImplementation((path) => {
    if (path === '/v1/users/me') return Promise.resolve({ language_code: 'ru' });
    if (path === '/v1/natal/profile/latest') return Promise.resolve({ id: 'profile-1' });
    return Promise.resolve({});
  });

  askOracle.mockResolvedValue(mockOracleResponse());
  fetchWalletSummary.mockResolvedValue({ balance_stars: 12, recent_entries: [] });
  fetchUserHistory.mockResolvedValue({ reports: [] });

  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Velaryx Oracle UI', () => {
  it('renders oracle home with new bottom tabs', () => {
    render(<App />);

    expect(screen.getByText('Velaryx')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Оракул' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Совместимость' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Профиль' })).toBeInTheDocument();
  });

  it('switches to compatibility and profile tabs', async () => {
    render(<App />);

    await waitFor(() => expect(apiRequest).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('tab', { name: 'Совместимость' }));
    expect(screen.getByRole('heading', { name: 'Совместимость' })).toBeInTheDocument();
    expect(screen.getByText('Рассчитать совместимость')).toBeDisabled();

    fireEvent.click(screen.getByRole('tab', { name: 'Профиль' }));
    expect(await screen.findByRole('heading', { name: 'Профиль' })).toBeInTheDocument();
    expect(await screen.findByText('12 ⭐')).toBeInTheDocument();
    expect(fetchWalletSummary).toHaveBeenCalled();
  });

  it('goes through oracle home -> loading -> result', async () => {
    let resolveOracle;
    askOracle.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveOracle = resolve;
      })
    );

    render(<App />);

    fireEvent.change(screen.getByPlaceholderText(/Стоит ли менять работу/i), {
      target: { value: 'Стоит ли менять работу?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Получить знак' }));

    expect(screen.getByText('Я слушаю воду…')).toBeInTheDocument();
    expect(askOracle).toHaveBeenCalledWith('Стоит ли менять работу?');

    resolveOracle(mockOracleResponse());

    expect(await screen.findByText('Знак получен')).toBeInTheDocument();
    expect(await screen.findByText('Шут')).toBeInTheDocument();
    expect(screen.getAllByText(/Суть:/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText('Задать новый вопрос'));
    await waitFor(() => {
      expect(screen.getByText('Velaryx')).toBeInTheDocument();
    });
  });
});
