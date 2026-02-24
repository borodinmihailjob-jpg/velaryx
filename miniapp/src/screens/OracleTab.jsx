import { useEffect, useState } from 'react';
import { fetchDailyForecast } from '../api';
import { BrandMark, GoldButton, InkButton, OrbLoader, ParchmentCard, TierBadge } from '../components/common/index.jsx';

const SERVICE_CARDS = [
  {
    id: 'horoscope',
    icon: '☀️',
    title: 'Гороскоп на сегодня',
    desc: 'Прогноз по знаку: любовь, деньги, энергия',
    premium: false,
  },
  {
    id: 'natal',
    icon: '🌙',
    title: 'Натальная карта',
    desc: 'Солнце, Луна, Асцендент и глубокий разбор',
    premium: true,
  },
  {
    id: 'tarot',
    icon: '🃏',
    title: 'Таро',
    desc: '3 карты бесплатно или 8-карточный премиум',
    premium: true,
  },
  {
    id: 'numerology',
    icon: '🔢',
    title: 'Нумерология',
    desc: 'Число судьбы и полный нумерологический разбор',
    premium: true,
  },
];

function DailyForecastBlock({ onDetails, hasProfile }) {
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!hasProfile) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    fetchDailyForecast()
      .then((data) => {
        if (!active) return;
        setForecast(data);
      })
      .catch(() => {
        if (!active) return;
        setError('Знак скрыт туманом. Попробуй позже.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [hasProfile]);

  if (!hasProfile) {
    return (
      <ParchmentCard className="daily-forecast-block">
        <div className="forecast-no-profile">
          <span style={{ fontSize: 32 }}>🌊</span>
          <p style={{ fontFamily: 'Cinzel, serif', margin: '8px 0 4px' }}>Знак дня</p>
          <p className="muted-text" style={{ marginBottom: 12 }}>
            Чтобы прогноз был точнее — добавь дату рождения
          </p>
          <InkButton onClick={onDetails}>Добавить</InkButton>
        </div>
      </ParchmentCard>
    );
  }

  if (loading) {
    return (
      <ParchmentCard className="daily-forecast-block">
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <OrbLoader />
          <p className="muted-text">Читаю воду…</p>
        </div>
      </ParchmentCard>
    );
  }

  if (error || !forecast) {
    return (
      <ParchmentCard className="daily-forecast-block">
        <p className="muted-text" style={{ textAlign: 'center' }}>{error || 'Прогноз недоступен'}</p>
        <InkButton onClick={() => window.location.reload()}>Попробовать снова</InkButton>
      </ParchmentCard>
    );
  }

  const payload = forecast.payload || {};
  const sunSign = payload.sun_sign || '';
  const mood = payload.mood || '';
  const focus = payload.focus || '';
  const energyScore = forecast.energy_score || 0;

  return (
    <ParchmentCard className="daily-forecast-block">
      <div className="forecast-header">
        <div>
          <p className="forecast-label">Знак дня</p>
          {sunSign ? (
            <h2 style={{ fontFamily: 'Cinzel, serif', margin: '4px 0', fontSize: 20 }}>{sunSign}</h2>
          ) : null}
          <div className="forecast-energy-badge">{energyScore}/100</div>
        </div>
        <div style={{ fontSize: 40 }}>🔮</div>
      </div>
      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="bullet-row">
          <span className="bullet-dot">●</span>
          <span><b>Суть дня:</b> {forecast.summary || 'Энергия формируется'}</span>
        </div>
        {mood ? (
          <div className="bullet-row">
            <span className="bullet-dot">●</span>
            <span><b>Что усилить:</b> {mood}</span>
          </div>
        ) : null}
        {focus ? (
          <div className="bullet-row">
            <span className="bullet-dot">●</span>
            <span><b>Акцент:</b> {focus}</span>
          </div>
        ) : null}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <GoldButton onClick={onDetails} style={{ flex: 1 }}>Подробнее</GoldButton>
        <InkButton onClick={() => {
          if (window.Telegram?.WebApp?.shareURL) {
            window.Telegram.WebApp.shareURL(
              window.location.href,
              `Мой прогноз дня: ${forecast.summary?.slice(0, 100) || 'Посмотри свой знак!'}`
            );
          }
        }}>Поделиться</InkButton>
      </div>
    </ParchmentCard>
  );
}

function ServiceCard({ card, onNavigate }) {
  return (
    <button
      type="button"
      className="service-card"
      onClick={() => onNavigate(card.id)}
      aria-label={card.title}
    >
      <div className="service-card-icon">{card.icon}</div>
      <div className="service-card-content">
        <div className="service-card-title">{card.title}</div>
        <div className="service-card-desc">{card.desc}</div>
      </div>
      <TierBadge premium={card.premium} />
    </button>
  );
}

export default function OracleTab({ onNavigate, hasProfile }) {
  return (
    <div className="screen">
      <div className="header-row">
        <div className="brand-mark" aria-hidden="true">
          <BrandMark />
        </div>
        <div>
          <h1 style={{ fontFamily: 'Cinzel, serif', fontSize: 24, margin: 0 }}>Velaryx</h1>
          <p style={{ fontSize: 12, color: 'var(--smoke-600)', margin: 0 }}>Оракул воды и времени</p>
        </div>
      </div>

      <DailyForecastBlock
        hasProfile={hasProfile}
        onDetails={() => onNavigate('horoscope')}
      />

      <div className="section-title">Сервисы</div>

      <div className="oracle-service-cards">
        {SERVICE_CARDS.map((card) => (
          <ServiceCard key={card.id} card={card} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  );
}
