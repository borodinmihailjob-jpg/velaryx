import { useEffect, useState } from 'react';
import { askOracle, fetchDailyForecast } from '../api';
import { BrandMark, Chip, GoldButton, InkButton, OrbLoader, ParchmentCard, Shell, TierBadge } from '../components/common/index.jsx';

const THEME_CHIPS = ['Любовь', 'Деньги', 'Выбор', 'Путь'];
const QUICK_QUESTIONS = [
  'Стоит ли писать первым(ой)?',
  'Где моя удача сейчас?',
  'Что мне важно понять сегодня?',
  'Какой шаг даст результат?',
];
const ENERGIES = ['Спокойствие', 'Смелость', 'Осторожность'];

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

function parseInterpretation(text) {
  const suteMatch = text.match(/Суть[:\s]+([^\n.]+)/i);
  const sdelaiMatch = text.match(/[Сс]дел[аа]й[:\s]+([^\n.]+)/i);
  const izbegaiMatch = text.match(/[Ии]збег[аa]й[:\s]+([^\n.]+)/i);
  if (suteMatch && sdelaiMatch && izbegaiMatch) {
    return {
      sute: suteMatch[1].trim(),
      sdelai: sdelaiMatch[1].trim(),
      izbegai: izbegaiMatch[1].trim(),
      body: text,
    };
  }
  const sentences = text.split(/[.!?]+/).filter((s) => s.trim()).slice(0, 3);
  return {
    sute: sentences[0]?.trim() || '',
    sdelai: sentences[1]?.trim() || '',
    izbegai: sentences[2]?.trim() || '',
    body: text,
  };
}

function OracleQuestionCard({ onSubmit }) {
  const [q, setQ] = useState('');

  return (
    <ParchmentCard>
      <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 18, margin: 0 }}>
        Спроси — и я покажу знак.
      </h2>
      <textarea
        className="input-field"
        style={{ width: '100%', minHeight: 80, resize: 'none', marginTop: 10 }}
        placeholder='Например: "Стоит ли менять работу?"'
        value={q}
        onChange={(e) => setQ(e.target.value)}
        maxLength={500}
      />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
        {THEME_CHIPS.map((c) => (
          <Chip key={c} label={c} onClick={() => setQ(c)} />
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
        {QUICK_QUESTIONS.map((p) => (
          <Chip key={p} label={p} onClick={() => setQ(p)} />
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
        <GoldButton onClick={() => onSubmit(q)} disabled={!q.trim()}>
          Получить знак
        </GoldButton>
        <InkButton onClick={() => onSubmit('Что важно знать мне сегодня?')}>
          Быстрый знак дня
        </InkButton>
      </div>
      <p className="muted-text" style={{ textAlign: 'center', marginTop: 6 }}>
        Это подсказка, а не приговор. Решение всегда твоё.
      </p>
    </ParchmentCard>
  );
}

function OracleLoadingView() {
  return (
    <div className="loading-screen">
      <OrbLoader />
      <h2 style={{ fontFamily: 'Cinzel, serif' }}>Я слушаю воду…</h2>
      <p className="muted-text" style={{ maxWidth: 280 }}>
        Появится знак — и станет легче дышать.
      </p>
    </div>
  );
}

function OracleResultView({ oracleData, onBack }) {
  const parsed = parseInterpretation(oracleData?.ai_interpretation || '');
  const cardNumber = oracleData?.cards?.[0]?.number ?? 0;
  const energy = ENERGIES[cardNumber % ENERGIES.length];
  const time = new Date().toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });

  return (
    <Shell title="Знак получен" sub={`Сегодня • ${time}`} onBack={onBack}>
      <ParchmentCard>
        <span className="badge">Твоя энергия: {energy}</span>
        <h2 style={{ fontFamily: 'Cinzel, serif', marginTop: 8 }}>
          {oracleData.cards[0].name}
        </h2>
        <p style={{ fontSize: 15, lineHeight: 1.6, marginTop: 8 }}>
          {parsed.body.slice(0, 200)}
        </p>
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {parsed.sute && (
            <div className="bullet-row">
              <span className="bullet-dot">●</span>
              <span><b>Суть:</b> {parsed.sute}</span>
            </div>
          )}
          {parsed.sdelai && (
            <div className="bullet-row">
              <span className="bullet-dot">●</span>
              <span><b>Сделай:</b> {parsed.sdelai}</span>
            </div>
          )}
          {parsed.izbegai && (
            <div className="bullet-row">
              <span className="bullet-dot">●</span>
              <span><b>Избегай:</b> {parsed.izbegai}</span>
            </div>
          )}
        </div>
      </ParchmentCard>

      <ParchmentCard className="upsell-card">
        <h3 style={{ fontFamily: 'Cinzel, serif' }}>Уточнить знак</h3>
        <p className="muted-text">Я открою скрытый фактор и лучший момент.</p>
        <GoldButton onClick={() => alert('Скоро')}>
          Открыть полный ответ • ⭐ Stars
        </GoldButton>
      </ParchmentCard>

      <InkButton onClick={() => alert('Скоро')}>Поделиться знаком</InkButton>
      <p
        style={{ textAlign: 'center', cursor: 'pointer', color: 'var(--azure-500)', fontSize: 14 }}
        onClick={onBack}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter') onBack(); }}
      >
        Задать новый вопрос
      </p>
    </Shell>
  );
}

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
      <span className="service-card-icon">{card.icon}</span>
      <div className="service-card-content">
        <div className="service-card-title">{card.title}</div>
        <div className="service-card-desc">{card.desc}</div>
      </div>
      <TierBadge premium={card.premium} />
    </button>
  );
}

export default function OracleTab({ onNavigate, hasProfile }) {
  const [subview, setSubview] = useState(null); // null | 'loading' | 'result'
  const [question, setQuestion] = useState('');
  const [oracleData, setOracleData] = useState(null);
  const [oracleError, setOracleError] = useState(null);

  const handleAskOracle = (q) => {
    setOracleError(null);
    setQuestion(q);
    setSubview('loading');
  };

  useEffect(() => {
    if (subview !== 'loading') return undefined;
    let active = true;
    askOracle(question)
      .then((data) => {
        if (!active) return;
        setOracleData(data);
        setSubview('result');
      })
      .catch((e) => {
        if (!active) return;
        setOracleError(e.message || 'Оракул не смог ответить. Попробуй ещё раз.');
        setSubview(null);
      });
    return () => { active = false; };
  }, [subview, question]);

  if (subview === 'loading') {
    return <OracleLoadingView />;
  }

  if (subview === 'result' && oracleData) {
    return <OracleResultView oracleData={oracleData} onBack={() => setSubview(null)} />;
  }

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

      {oracleError && (
        <div className="error-banner">{oracleError}</div>
      )}

      <OracleQuestionCard onSubmit={handleAskOracle} />

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
