import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useLaunchParams } from '@telegram-apps/sdk-react';

import { apiRequest } from './api';

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || 'replace_me_bot';
const APP_NAME = import.meta.env.VITE_APP_NAME || 'app';
const TAROT_LOADING_GIF = import.meta.env.VITE_TAROT_LOADING_GIF || '';

const pageVariants = {
  initial: { opacity: 0, y: 20, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } }
};

const staggerContainer = { animate: { transition: { staggerChildren: 0.06 } } };
const staggerItem = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } }
};

const TIMEZONES = [
  'Europe/Moscow', 'Europe/Kaliningrad', 'Europe/Samara', 'Asia/Yekaterinburg',
  'Asia/Omsk', 'Asia/Krasnoyarsk', 'Asia/Irkutsk', 'Asia/Yakutsk',
  'Asia/Vladivostok', 'Asia/Magadan', 'Asia/Kamchatka',
  'Europe/Minsk', 'Europe/Kiev', 'Asia/Almaty', 'Asia/Tashkent',
  'Asia/Baku', 'Asia/Tbilisi', 'Asia/Yerevan', 'Asia/Bishkek',
  'Europe/Chisinau', 'UTC'
];

const TZ_LABELS = {
  'Europe/Moscow': 'Москва (UTC+3)',
  'Europe/Kaliningrad': 'Калининград (UTC+2)',
  'Europe/Samara': 'Самара (UTC+4)',
  'Asia/Yekaterinburg': 'Екатеринбург (UTC+5)',
  'Asia/Omsk': 'Омск (UTC+6)',
  'Asia/Krasnoyarsk': 'Красноярск (UTC+7)',
  'Asia/Irkutsk': 'Иркутск (UTC+8)',
  'Asia/Yakutsk': 'Якутск (UTC+9)',
  'Asia/Vladivostok': 'Владивосток (UTC+10)',
  'Asia/Magadan': 'Магадан (UTC+11)',
  'Asia/Kamchatka': 'Камчатка (UTC+12)',
  'Europe/Minsk': 'Минск (UTC+3)',
  'Europe/Kiev': 'Киев (UTC+2)',
  'Asia/Almaty': 'Алматы (UTC+6)',
  'Asia/Tashkent': 'Ташкент (UTC+5)',
  'Asia/Baku': 'Баку (UTC+4)',
  'Asia/Tbilisi': 'Тбилиси (UTC+4)',
  'Asia/Yerevan': 'Ереван (UTC+4)',
  'Asia/Bishkek': 'Бишкек (UTC+6)',
  'Europe/Chisinau': 'Кишинёв (UTC+2)',
  'UTC': 'UTC'
};

function buildStartAppLink(token) {
  return `https://t.me/${BOT_USERNAME}/${APP_NAME}?startapp=${token}`;
}

function shareLink(url, text) {
  const tgShare = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  if (window.Telegram?.WebApp?.openTelegramLink) {
    window.Telegram.WebApp.openTelegramLink(tgShare);
    return;
  }
  window.open(tgShare, '_blank');
}

function useStartParam() {
  let sdkStartParam = null;
  try {
    const params = useLaunchParams();
    sdkStartParam = params?.startParam || null;
  } catch {
    sdkStartParam = null;
  }

  const fromQuery = new URLSearchParams(window.location.search).get('startapp');
  const fromUnsafe = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
  return sdkStartParam || fromUnsafe || fromQuery || null;
}

function startParamToView(startParam) {
  if (!startParam) return null;
  const mapping = {
    sc_onboarding: 'onboarding',
    sc_natal: 'natal',
    sc_stories: 'stories',
    sc_tarot: 'tarot'
  };
  return mapping[startParam] || null;
}

function Hint({ text }) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="hint-tooltip"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onTouchStart={() => setShow(!show)}
    >
      <span className="hint-icon">?</span>
      {show && <span className="hint-text">{text}</span>}
    </span>
  );
}

function Shell({ title, subtitle, children, onBack, className = '' }) {
  return (
    <motion.main className={`screen ${className}`.trim()} variants={pageVariants} initial="initial" animate="animate" exit="exit">
      <header className="screen-head">
        <div>
          {onBack && (
            <button className="back-btn" onClick={onBack} style={{ marginBottom: 8 }}>
              &#8592; Назад
            </button>
          )}
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </header>
      {children}
    </motion.main>
  );
}

function Onboarding({ onComplete }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    birth_date: '',
    birth_time: '12:00',
    birth_place: '',
    latitude: '',
    longitude: '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow'
  });

  const [citySuggestions, setCitySuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [citySelected, setCitySelected] = useState(false);
  const [showManualCoords, setShowManualCoords] = useState(false);
  const debounceRef = useRef(null);
  const wrapperRef = useRef(null);

  const searchCities = useCallback((query) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.length < 1) {
      setCitySuggestions([]);
      setShowSuggestions(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      try {
        const results = await apiRequest(`/v1/geo/cities?q=${encodeURIComponent(query)}`);
        setCitySuggestions(results);
        setShowSuggestions(results.length > 0);
      } catch {
        setCitySuggestions([]);
      }
    }, 300);
  }, []);

  const handleCityInput = (value) => {
    setForm((prev) => ({ ...prev, birth_place: value }));
    setCitySelected(false);
    searchCities(value);
  };

  const selectCity = (city) => {
    setForm((prev) => ({
      ...prev,
      birth_place: city.name,
      latitude: String(city.latitude),
      longitude: String(city.longitude),
      timezone: city.timezone
    }));
    setCitySelected(true);
    setShowSuggestions(false);
    setCitySuggestions([]);
  };

  useEffect(() => {
    const handleClick = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('touchstart', handleClick);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('touchstart', handleClick);
    };
  }, []);

  const canSubmit = form.birth_date && form.birth_place && form.latitude && form.longitude && form.timezone;

  const submit = async () => {
    if (!canSubmit) return;
    setError('');
    setLoading(true);
    try {
      const profile = await apiRequest('/v1/natal/profile', {
        method: 'POST',
        body: JSON.stringify({
          birth_date: form.birth_date,
          birth_time: form.birth_time || '12:00',
          birth_place: form.birth_place,
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          timezone: form.timezone
        })
      });

      await apiRequest('/v1/natal/calculate', {
        method: 'POST',
        body: JSON.stringify({ profile_id: profile.id })
      });

      localStorage.setItem('onboarding_complete', '1');
      onComplete();
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Shell title="Ваша звезда" subtitle="Заполните данные рождения для персональной карты">
      <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
        <motion.div variants={staggerItem}>
          <label>
            Дата рождения
            <Hint text="Укажите точную дату для составления натальной карты" />
            <input type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} />
          </label>
        </motion.div>

        <motion.div variants={staggerItem}>
          <label>
            Время рождения
            <Hint text="Если не знаете точного времени, оставьте 12:00" />
            <input type="time" value={form.birth_time} onChange={(e) => setForm({ ...form, birth_time: e.target.value })} />
            <span className="input-hint">Если не знаете точно, оставьте 12:00</span>
          </label>
        </motion.div>

        <motion.div variants={staggerItem}>
          <div className="city-autocomplete" ref={wrapperRef}>
            <label>
              Город рождения
              <Hint text="Начните вводить название и выберите из списка" />
              <input
                placeholder="Начните вводить город..."
                value={form.birth_place}
                onChange={(e) => handleCityInput(e.target.value)}
                onFocus={() => { if (citySuggestions.length > 0) setShowSuggestions(true); }}
                autoComplete="off"
              />
            </label>

            <AnimatePresence>
              {showSuggestions && citySuggestions.length > 0 && (
                <motion.ul
                  className="city-dropdown"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  {citySuggestions.map((city) => (
                    <li key={`${city.name}-${city.latitude}-${city.longitude}`} onClick={() => selectCity(city)}>
                      <span className="city-name">{city.name}</span>
                      <span className="city-tz">{TZ_LABELS[city.timezone] || city.timezone}</span>
                    </li>
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>

            {citySelected && (
              <span className="input-hint" style={{ color: 'var(--ok)' }}>
                Координаты и часовой пояс заполнены автоматически
              </span>
            )}
          </div>
        </motion.div>

        <motion.div variants={staggerItem}>
          <label>
            Часовой пояс
            <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{TZ_LABELS[tz] || tz}</option>
              ))}
            </select>
          </label>
        </motion.div>

        {!showManualCoords && !citySelected && form.birth_place && (
          <motion.div variants={staggerItem}>
            <button className="profile-toggle" onClick={() => setShowManualCoords(true)} type="button">
              Нет моего города? Указать координаты вручную
            </button>
          </motion.div>
        )}

        {(showManualCoords || (!citySelected && form.latitude)) && (
          <motion.div variants={staggerItem} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
            <div className="grid-2">
              <label>
                Широта
                <input
                  placeholder="55.7558"
                  value={form.latitude}
                  onChange={(e) => setForm({ ...form, latitude: e.target.value })}
                  inputMode="decimal"
                />
              </label>
              <label>
                Долгота
                <input
                  placeholder="37.6173"
                  value={form.longitude}
                  onChange={(e) => setForm({ ...form, longitude: e.target.value })}
                  inputMode="decimal"
                />
              </label>
            </div>
          </motion.div>
        )}

        <motion.div variants={staggerItem}>
          <button className="cta" onClick={submit} disabled={loading || !canSubmit}>
            {loading ? 'Считаем карту...' : 'Продолжить'}
          </button>
        </motion.div>

        {error && (
          <motion.p className="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {error}
          </motion.p>
        )}
      </motion.div>
    </Shell>
  );
}

function Dashboard({ onOpenNatal, onOpenStories, onOpenTarot, onResetOnboarding }) {
  const menuItems = [
    { icon: '✨', label: 'Натальная карта', hint: 'Полный персональный разбор', action: onOpenNatal },
    { icon: '🌙', label: 'Сторис дня', hint: 'Короткие персональные инсайты', action: onOpenStories },
    { icon: '🃏', label: 'Таро-расклад', hint: 'Карты с пояснениями и анимацией', action: onOpenTarot }
  ];

  return (
    <Shell title="Созвездие" subtitle="Астрология и таро в одном потоке.">
      <motion.div className="card-grid" variants={staggerContainer} initial="initial" animate="animate">
        {menuItems.map((item) => (
          <motion.button
            key={item.label}
            className="menu-btn"
            onClick={item.action}
            variants={staggerItem}
            whileTap={{ scale: 0.97 }}
          >
            <span className="menu-icon">{item.icon}</span>
            <span className="menu-text">
              <span>{item.label}</span>
              <span className="menu-hint">{item.hint}</span>
            </span>
          </motion.button>
        ))}
      </motion.div>

      <button className="profile-toggle" onClick={onResetOnboarding}>Обновить данные рождения</button>
    </Shell>
  );
}

function NatalChart({ onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chart, setChart] = useState(null);

  useEffect(() => {
    apiRequest('/v1/natal/full')
      .then(setChart)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Shell title="Натальная карта" subtitle="Подробный персональный разбор" onBack={onBack}>
      {loading && <p className="loading-text">Собираем карту...</p>}
      {error && <p className="error">{error}</p>}

      {chart && (
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
          <motion.div className="chip-row" variants={staggerItem} style={{ justifyContent: 'center' }}>
            <span>☀ {chart.sun_sign}</span>
            <span>☽ {chart.moon_sign}</span>
            <span>↑ {chart.rising_sign}</span>
          </motion.div>

          {chart.wheel_chart_url && (
            <motion.article className="story-card" variants={staggerItem}>
              <img src={chart.wheel_chart_url} alt="Natal wheel" style={{ width: '100%', borderRadius: 12 }} />
            </motion.article>
          )}

          {(chart.interpretation_sections || []).map((section, idx) => (
            <motion.article className="story-card" variants={staggerItem} key={`${section.title}-${idx}`}>
              <p className="section-title">{section.icon} {section.title}</p>
              <p>{section.text}</p>
            </motion.article>
          ))}
        </motion.div>
      )}
    </Shell>
  );
}

function Stories({ onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    apiRequest('/v1/forecast/stories')
      .then((data) => {
        setPayload(data);
        setIndex(0);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const slides = payload?.slides || [];
  const slide = slides[index];

  return (
    <Shell title="Сторис дня" subtitle="Краткий персональный поток на сегодня" onBack={onBack}>
      {loading && <p className="loading-text">Готовим сторис...</p>}
      {error && <p className="error">{error}</p>}

      {slide && (
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
          <motion.article className="story-card" variants={staggerItem}>
            <small>{payload.date}</small>
            <p className="section-title">{slide.title}</p>
            <p>{slide.body}</p>
            {slide.badge && <div className="chip-row"><span>{slide.badge}</span></div>}
          </motion.article>

          <div className="grid-2">
            <button className="ghost" disabled={index === 0} onClick={() => setIndex((prev) => Math.max(0, prev - 1))}>Назад</button>
            <button
              className="cta"
              disabled={index >= slides.length - 1}
              onClick={() => setIndex((prev) => Math.min(slides.length - 1, prev + 1))}
            >
              Дальше
            </button>
          </div>

          <button
            className="ghost"
            onClick={() => shareLink(buildStartAppLink('sc_stories'), 'Посмотри мой астросторис-день ✨')}
          >
            Поделиться
          </button>
        </motion.div>
      )}
    </Shell>
  );
}

function Tarot({ onBack }) {
  const [question, setQuestion] = useState('');
  const [reading, setReading] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [gifFailed, setGifFailed] = useState(false);

  const draw = async () => {
    setError('');
    setGifFailed(false);
    setLoading(true);
    try {
      const data = await apiRequest('/v1/tarot/draw', {
        method: 'POST',
        body: JSON.stringify({ spread_type: 'three_card', question })
      });
      setReading(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Shell
      title="Таро-расклад"
      subtitle="Задайте вопрос и вытяните 3 карты"
      onBack={onBack}
      className="tarot-screen"
    >
      <div className="stack">
        <label>
          Ваш вопрос
          <Hint text="Чем точнее формулировка, тем практичнее трактовка" />
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Какой следующий шаг в отношениях/работе?"
          />
        </label>

        <button className="cta" onClick={draw} disabled={loading}>
          {loading ? 'Тасуем карты...' : 'Сделать расклад'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {loading && (
        <motion.div
          className="fortune-loader"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          {TAROT_LOADING_GIF && !gifFailed ? (
            <motion.div
              className="fortune-gif-stage"
              initial={{ opacity: 0.5, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
            >
              <img
                className="fortune-loader-gif"
                src={TAROT_LOADING_GIF}
                alt="Tarot loading"
                loading="eager"
                onError={() => setGifFailed(true)}
              />
            </motion.div>
          ) : (
            <div className="fortune-stage" aria-hidden="true">
              <span className="fortune-particle particle-1" />
              <span className="fortune-particle particle-2" />
              <span className="fortune-particle particle-3" />
              <span className="fortune-particle particle-4" />
              <span className="fortune-particle particle-5" />

              <div className="fortune-orbit orbit-1"><span className="orbit-card" /></div>
              <div className="fortune-orbit orbit-2"><span className="orbit-card" /></div>
              <div className="fortune-orbit orbit-3"><span className="orbit-card" /></div>

              <motion.div
                className="fortune-orb"
                animate={{ y: [0, -6, 0], scale: [1, 1.02, 1] }}
                transition={{ repeat: Infinity, duration: 2.8, ease: 'easeInOut' }}
              >
                <div className="fortune-orb-core" />
              </motion.div>
            </div>
          )}
          <p className="fortune-loader-title">Сфера открывает знаки...</p>
          <p className="fortune-loader-subtitle">Карты складываются в ответ</p>
        </motion.div>
      )}

      {reading && (
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate" style={{ gap: 12 }}>
          {(reading.cards || []).length > 0 && <p className="section-title">Ваш расклад</p>}
          {(reading.cards || []).map((card, idx) => (
            <motion.article key={`${card.card_name}-${idx}`} className="tarot-card" variants={staggerItem}>
              {card.image_url && (
                <div className="tarot-image-frame">
                  <img
                    src={card.image_url}
                    alt={card.card_name}
                    className={`tarot-image ${card.is_reversed ? 'reversed' : ''}`}
                    loading="lazy"
                  />
                </div>
              )}
              <span className="tarot-position">{card.slot_label}</span>
              <span className="tarot-name">{card.card_name}</span>
              <span className={`tarot-orientation ${card.is_reversed ? 'reversed' : 'upright'}`}>
                {card.is_reversed ? '↻ Перевёрнутая' : '↑ Прямая'}
              </span>
              <p className="tarot-meaning">{card.meaning}</p>
            </motion.article>
          ))}
          {reading.ai_interpretation && (
            <motion.article className="story-card" variants={staggerItem}>
              <p className="section-title">Интерпретация</p>
              <p>{reading.ai_interpretation}</p>
              {reading.llm_provider && <small>Источник: {reading.llm_provider}</small>}
            </motion.article>
          )}
        </motion.div>
      )}
    </Shell>
  );
}

export default function App() {
  const startParam = useStartParam();
  const [view, setView] = useState('dashboard');

  const onboardingDone = useMemo(() => localStorage.getItem('onboarding_complete') === '1', []);
  const [hasOnboarding, setHasOnboarding] = useState(onboardingDone);

  useEffect(() => {
    const mapped = startParamToView(startParam);
    if (mapped) {
      setView(mapped);
      return;
    }
    if (!onboardingDone) {
      setView('onboarding');
    }
  }, [startParam, onboardingDone]);

  if (view === 'onboarding' || !hasOnboarding) {
    return <Onboarding onComplete={() => { setHasOnboarding(true); setView('dashboard'); }} />;
  }

  if (view === 'natal') return <NatalChart onBack={() => setView('dashboard')} />;
  if (view === 'stories') return <Stories onBack={() => setView('dashboard')} />;
  if (view === 'tarot') return <Tarot onBack={() => setView('dashboard')} />;

  return (
    <Dashboard
      onOpenNatal={() => setView('natal')}
      onOpenStories={() => setView('stories')}
      onOpenTarot={() => setView('tarot')}
      onResetOnboarding={() => {
        localStorage.removeItem('onboarding_complete');
        setHasOnboarding(false);
        setView('onboarding');
      }}
    />
  );
}
