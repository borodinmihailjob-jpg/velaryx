import { useEffect, useState } from 'react';
import { fetchHoroscope } from '../api';
import {
  ErrorBanner, GoldButton, InkButton, OrbLoader, ParchmentCard, Shell, TierBadge,
} from '../components/common/index.jsx';

function SlideCard({ slide }) {
  return (
    <ParchmentCard>
      <div className="slide-header">
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0, fontSize: 16 }}>{slide.title}</h3>
        {slide.badge ? <span className="badge">{slide.badge}</span> : null}
      </div>
      <p style={{ marginTop: 10, lineHeight: 1.6 }}>{slide.body}</p>
      {slide.tip ? (
        <div className="bullet-row" style={{ marginTop: 8 }}>
          <span className="bullet-dot" style={{ color: 'var(--gold-500)' }}>✦</span>
          <span><b>Что сделать:</b> {slide.tip}</span>
        </div>
      ) : null}
      {slide.avoid ? (
        <div className="bullet-row" style={{ marginTop: 4 }}>
          <span className="bullet-dot" style={{ color: 'var(--smoke-600)' }}>✦</span>
          <span><b>Избегай:</b> {slide.avoid}</span>
        </div>
      ) : null}
      {slide.timing ? (
        <div className="timing-chip" style={{ marginTop: 8 }}>
          🕐 {slide.timing}
        </div>
      ) : null}
    </ParchmentCard>
  );
}

export default function HoroscopeScreen({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchHoroscope()
      .then((d) => {
        if (!active) return;
        setData(d);
      })
      .catch((e) => {
        if (!active) return;
        setError(String(e?.message || 'Знак скрыт туманом. Проверь соединение и попробуй снова.'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  if (loading) {
    return (
      <Shell title="Гороскоп" onBack={onBack}>
        <OrbLoader />
        <p className="muted-text" style={{ textAlign: 'center' }}>Читаю звёзды…</p>
      </Shell>
    );
  }

  const slides = data?.slides || [];

  return (
    <Shell
      title="Гороскоп на сегодня"
      sub={data?.date ? new Date(data.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) : ''}
      onBack={onBack}
    >
      <ErrorBanner message={error} />

      {slides.length === 0 && !error ? (
        <ParchmentCard>
          <p className="muted-text">Прогноз формируется. Попробуй позже.</p>
        </ParchmentCard>
      ) : null}

      {slides.map((slide, i) => (
        <SlideCard key={i} slide={slide} />
      ))}

      <ParchmentCard className="upsell-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0, fontSize: 15 }}>Прогноз на 7 дней</h3>
            <p className="muted-text" style={{ margin: '4px 0 0' }}>Подробный план на неделю вперёд</p>
          </div>
          <TierBadge premium />
        </div>
        <GoldButton
          onClick={() => window.alert('Скоро')}
          style={{ marginTop: 12 }}
        >
          Открыть прогноз ⭐
        </GoldButton>
      </ParchmentCard>

      <InkButton onClick={() => {
        if (window.Telegram?.WebApp?.shareURL) {
          window.Telegram.WebApp.shareURL(window.location.href, 'Мой гороскоп на сегодня');
        }
      }}>
        Поделиться
      </InkButton>
    </Shell>
  );
}
