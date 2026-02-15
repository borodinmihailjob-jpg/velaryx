import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLaunchParams } from '@telegram-apps/sdk-react';

import { apiRequest } from './api';

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || 'replace_me_bot';
const APP_NAME = import.meta.env.VITE_APP_NAME || 'app';

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

/* ===== Hint Tooltip ===== */
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

/* ===== Page transitions ===== */
const pageVariants = {
  initial: { opacity: 0, y: 20, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } }
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.06 } }
};

const staggerItem = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } }
};

/* ===== Shell ===== */
function Shell({ title, subtitle, children, onBack }) {
  return (
    <motion.main
      className="screen"
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
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

/* ===== Timezone list ===== */
const TIMEZONES = [
  'Europe/Moscow', 'Europe/Kaliningrad', 'Europe/Samara', 'Asia/Yekaterinburg',
  'Asia/Omsk', 'Asia/Krasnoyarsk', 'Asia/Irkutsk', 'Asia/Yakutsk',
  'Asia/Vladivostok', 'Asia/Magadan', 'Asia/Kamchatka',
  'Europe/Minsk', 'Europe/Kiev', 'Asia/Almaty', 'Asia/Tashkent',
  'Asia/Baku', 'Asia/Tbilisi', 'Asia/Yerevan', 'Asia/Bishkek',
  'Europe/Chisinau', 'UTC',
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
  'UTC': 'UTC',
};

/* ===== Onboarding ===== */
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

  /* City autocomplete */
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
      timezone: city.timezone,
    }));
    setCitySelected(true);
    setShowSuggestions(false);
    setCitySuggestions([]);
  };

  /* Close dropdown on outside click */
  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
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

  const canSubmit =
    form.birth_date &&
    form.birth_place &&
    form.latitude &&
    form.longitude &&
    form.timezone;

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

      const chart = await apiRequest('/v1/natal/calculate', {
        method: 'POST',
        body: JSON.stringify({ profile_id: profile.id })
      });

      localStorage.setItem('onboarding_complete', '1');
      onComplete(chart);
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
            <input
              type="date"
              value={form.birth_date}
              onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
            />
          </label>
        </motion.div>

        <motion.div variants={staggerItem}>
          <label>
            Время рождения
            <Hint text="Если не знаете точного времени, оставьте 12:00" />
            <input
              type="time"
              value={form.birth_time}
              onChange={(e) => setForm({ ...form, birth_time: e.target.value })}
            />
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
                    <li key={city.name} onClick={() => selectCity(city)}>
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
            <select
              value={form.timezone}
              onChange={(e) => setForm({ ...form, timezone: e.target.value })}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{TZ_LABELS[tz] || tz}</option>
              ))}
            </select>
          </label>
        </motion.div>

        {!showManualCoords && !citySelected && form.birth_place && (
          <motion.div variants={staggerItem}>
            <button
              className="profile-toggle"
              onClick={() => setShowManualCoords(true)}
              type="button"
            >
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

/* ===== Dashboard ===== */
function Dashboard({ onOpenNatal, onOpenStories, onOpenTarot, onOpenWishlist, onResetOnboarding }) {
  const [compatLink, setCompatLink] = useState('');
  const [compatLoading, setCompatLoading] = useState(false);
  const [error, setError] = useState('');

  const createCompatLink = async () => {
    setError('');
    setCompatLoading(true);
    try {
      const invite = await apiRequest('/v1/compat/invites', {
        method: 'POST',
        body: JSON.stringify({ ttl_days: 7, max_uses: 1 })
      });
      const url = buildStartAppLink(invite.token);
      setCompatLink(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setCompatLoading(false);
    }
  };

  const menuItems = [
    {
      icon: '\u2728',
      label: 'Натальная карта',
      hint: 'Полный разбор по планетам',
      action: onOpenNatal
    },
    {
      icon: '\uD83C\uDF19',
      label: 'Ежедневный прогноз',
      hint: 'Энергия и фокус дня',
      action: onOpenStories
    },
    {
      icon: '\uD83D\uDC9C',
      label: 'Наше созвездие',
      hint: 'Проверьте совместимость',
      action: createCompatLink
    },
    {
      icon: '\uD83C\uDFB4',
      label: 'Таро-расклад',
      hint: 'Расклад на 3 карты',
      action: onOpenTarot
    },
    {
      icon: '\uD83C\uDF81',
      label: 'Карта желаний',
      hint: 'Создайте и делитесь',
      action: onOpenWishlist
    }
  ];

  return (
    <Shell title="Созвездие" subtitle="Платформа, где связи становятся видимыми.">
      <motion.div className="card-grid" variants={staggerContainer} initial="initial" animate="animate">
        {menuItems.map((item, idx) => (
          <motion.button
            key={idx}
            className="menu-btn"
            onClick={item.action}
            variants={staggerItem}
            whileTap={{ scale: 0.97 }}
            disabled={item.label === 'Наше созвездие' && compatLoading}
          >
            <span className="menu-icon">{item.icon}</span>
            <span className="menu-text">
              <span>{item.label}</span>
              <span className="menu-hint">{item.hint}</span>
            </span>
          </motion.button>
        ))}
      </motion.div>

      <AnimatePresence>
        {compatLink && (
          <motion.div
            className="story-card"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <p className="section-title">Ссылка для партнёра</p>
            <p className="link-box">{compatLink}</p>
            <button className="ghost" onClick={() => shareLink(compatLink, 'Проверь нашу совместимость \u{1F4AB}')}>
              Поделиться созвездием
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {error && <p className="error">{error}</p>}

      <button className="profile-toggle" onClick={onResetOnboarding}>
        Мой профиль &#x25BE;
      </button>
    </Shell>
  );
}

/* ===== Natal Chart ===== */
function NatalChart({ onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chart, setChart] = useState(null);

  useEffect(() => {
    apiRequest('/v1/natal/latest')
      .then(setChart)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const interpretation = chart?.chart_payload?.interpretation;
  const keyAspects = interpretation?.key_aspects || [];

  return (
    <Shell title="Натальная карта" subtitle="Ваш персональный астрологический профиль" onBack={onBack}>
      {loading && <p className="loading-text">Собираем карту...</p>}
      {error && <p className="error">{error}</p>}

      {chart && (
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
          <motion.div className="chip-row" variants={staggerItem} style={{ justifyContent: 'center' }}>
            <span>&#x2600; Солнце: {chart.sun_sign}</span>
            <span>&#x263D; Луна: {chart.moon_sign}</span>
            <span>&#x2191; Асцендент: {chart.rising_sign}</span>
          </motion.div>

          {interpretation?.summary && (
            <motion.article className="story-card" variants={staggerItem}>
              <p>{interpretation.summary}</p>
            </motion.article>
          )}

          {interpretation?.sun_explanation && (
            <motion.article className="story-card" variants={staggerItem}>
              <p><strong>Солнце:</strong> {interpretation.sun_explanation}</p>
              <p><strong>Луна:</strong> {interpretation.moon_explanation}</p>
              <p><strong>Асцендент:</strong> {interpretation.rising_explanation}</p>
            </motion.article>
          )}

          {keyAspects.length > 0 && (
            <motion.article className="story-card" variants={staggerItem}>
              <p className="section-title">Ключевые аспекты</p>
              {keyAspects.map((line, idx) => (
                <p key={idx} style={{ marginTop: idx ? 6 : 0 }}>{line}</p>
              ))}
            </motion.article>
          )}
        </motion.div>
      )}
    </Shell>
  );
}

/* ===== Stories (Daily Forecast) ===== */
function Stories({ onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [forecast, setForecast] = useState(null);

  useEffect(() => {
    apiRequest('/v1/forecast/daily')
      .then(setForecast)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Shell title="Моя звезда" subtitle="Персональный ежедневный прогноз" onBack={onBack}>
      {loading && <p className="loading-text">Читаем звёзды...</p>}
      {error && <p className="error">{error}</p>}

      {forecast && (
        <motion.div
          className="stack"
          variants={staggerContainer}
          initial="initial"
          animate="animate"
        >
          <motion.div variants={staggerItem}>
            <div className="energy-circle" style={{ '--energy-pct': `${forecast.energy_score}%` }}>
              <span className="energy-value">{forecast.energy_score}</span>
            </div>
            <p style={{ textAlign: 'center', marginTop: 8, fontSize: '0.85rem' }}>Энергия дня</p>
          </motion.div>

          <motion.article className="story-card" variants={staggerItem}>
            <small>{forecast.date}</small>
            <p>{forecast.summary}</p>
          </motion.article>

          <motion.div className="chip-row" variants={staggerItem} style={{ justifyContent: 'center' }}>
            {forecast.payload?.sun_sign && <span>&#x2600; {forecast.payload.sun_sign}</span>}
            {forecast.payload?.moon_sign && <span>&#x263D; {forecast.payload.moon_sign}</span>}
            {forecast.payload?.rising_sign && <span>&#x2191; {forecast.payload.rising_sign}</span>}
          </motion.div>
        </motion.div>
      )}
    </Shell>
  );
}

/* ===== Tarot ===== */
function Tarot({ onBack }) {
  const [question, setQuestion] = useState('');
  const [reading, setReading] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const draw = async () => {
    setError('');
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
    <Shell title="Таро-расклад" subtitle="Задайте вопрос и вытяните 3 карты" onBack={onBack}>
      <div className="stack">
        <label>
          Ваш вопрос
          <Hint text="Сформулируйте открытый вопрос, избегая &laquo;да/нет&raquo;" />
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="На чём сфокусироваться сегодня?"
          />
          <span className="input-hint">Можно оставить пустым для общего расклада</span>
        </label>

        <button className="cta" onClick={draw} disabled={loading}>
          {loading ? 'Тасуем карты...' : 'Сделать расклад'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {reading && (
        <motion.div
          className="stack"
          variants={staggerContainer}
          initial="initial"
          animate="animate"
          style={{ gap: 12 }}
        >
          <p className="section-title">Ваш расклад</p>
          {reading.cards.map((card, idx) => (
            <motion.article
              key={`${card.card_name}-${idx}`}
              className="tarot-card"
              variants={staggerItem}
            >
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
                {card.is_reversed ? '\u21BB Перевёрнутая' : '\u2191 Прямая'}
              </span>
              <p className="tarot-meaning">{card.meaning}</p>
            </motion.article>
          ))}
        </motion.div>
      )}
    </Shell>
  );
}

/* ===== Compatibility Landing ===== */
function CompatibilityLanding({ token }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const start = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/v1/compat/start', {
        method: 'POST',
        body: JSON.stringify({ invite_token: token })
      });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const shareOwnLink = async () => {
    try {
      const invite = await apiRequest('/v1/compat/invites', {
        method: 'POST',
        body: JSON.stringify({ ttl_days: 7, max_uses: 1 })
      });
      const link = buildStartAppLink(invite.token);
      shareLink(link, 'Твоя очередь проверить совместимость \u{1F4AB}');
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <Shell title="Наше созвездие" subtitle="Узнайте вашу астрологическую совместимость">
      {!result && (
        <>
          <div className="compat-hero">
            <div className="compat-constellation">
              <motion.div
                className="compat-star"
                animate={{ y: [-4, 4, -4] }}
                transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
              />
              <motion.div
                className="compat-star"
                animate={{ y: [3, -5, 3] }}
                transition={{ repeat: Infinity, duration: 3.5, ease: 'easeInOut', delay: 0.5 }}
              />
              <motion.div
                className="compat-star"
                animate={{ y: [-3, 4, -3] }}
                transition={{ repeat: Infinity, duration: 2.8, ease: 'easeInOut', delay: 1 }}
              />
            </div>
          </div>

          <button className="cta" onClick={start} disabled={loading}>
            {loading ? 'Считаем звёзды...' : 'Узнать совместимость'}
          </button>
        </>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <motion.div
          className="stack"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="compat-hero">
            <div className="compat-constellation">
              <motion.div
                className="compat-star"
                animate={{ y: [-4, 4, -4] }}
                transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
              />
              <motion.div
                className="compat-star"
                animate={{ y: [3, -5, 3] }}
                transition={{ repeat: Infinity, duration: 3.5, ease: 'easeInOut', delay: 0.5 }}
              />
              <motion.div
                className="compat-star"
                animate={{ y: [-3, 4, -3] }}
                transition={{ repeat: Infinity, duration: 2.8, ease: 'easeInOut', delay: 1 }}
              />
            </div>
            <motion.span
              className="compat-score"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            >
              {result.score}%
            </motion.span>
            <span className="compat-score-label">Совместимость</span>
          </div>

          {result.summary && (
            <div className="story-card">
              <p>{result.summary}</p>
            </div>
          )}

          {result.strengths && result.strengths.length > 0 && (
            <motion.div className="compat-section" variants={staggerItem}>
              <h3>Ваши сильные стороны</h3>
              <ul>
                {result.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </motion.div>
          )}

          {result.growth_areas && result.growth_areas.length > 0 && (
            <motion.div className="compat-section" variants={staggerItem}>
              <h3>Точки роста</h3>
              <ul>
                {result.growth_areas.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </motion.div>
          )}

          <button className="ghost" onClick={shareOwnLink}>
            Поделиться созвездием
          </button>
        </motion.div>
      )}
    </Shell>
  );
}

/* ===== Wishlist Landing ===== */
function WishlistLanding({ token, onBack }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [reserved, setReserved] = useState('');
  const [reserving, setReserving] = useState('');

  useEffect(() => {
    apiRequest(`/v1/public/wishlists/${token}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [token]);

  const reserve = async (itemId) => {
    setError('');
    setReserving(itemId);
    try {
      await apiRequest(`/v1/public/wishlists/${token}/items/${itemId}/reserve`, {
        method: 'POST',
        body: JSON.stringify({ reserver_name: 'Mini App User' })
      });
      setReserved(itemId);
      const refreshed = await apiRequest(`/v1/public/wishlists/${token}`);
      setData(refreshed);
    } catch (e) {
      setError(e.message);
    } finally {
      setReserving('');
    }
  };

  return (
    <Shell
      title="Карта желаний"
      subtitle={data ? data.title : 'Загрузка...'}
      onBack={onBack}
    >
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="loading-text">Загружаем желания...</p>}

      {data && (
        <>
          <motion.div
            className="item-grid"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            {data.items.map((item) => (
              <motion.article
                key={item.id}
                className="item-card"
                variants={staggerItem}
                whileTap={{ scale: 0.97 }}
              >
                <strong>{item.title}</strong>
                <span className="item-price">
                  {item.budget_cents ? `${(item.budget_cents / 100).toLocaleString('ru-RU')} \u20BD` : 'Без бюджета'}
                </span>
                <span className={`status-badge ${item.status === 'reserved' ? 'reserved' : 'free'}`}>
                  {item.status === 'reserved' ? 'Забронировано' : 'Свободно'}
                </span>
                <button
                  className={item.status === 'reserved' ? 'ghost' : 'cta'}
                  disabled={item.status === 'reserved' || reserving === item.id}
                  onClick={() => reserve(item.id)}
                  style={{ padding: '10px 14px', fontSize: '0.82rem' }}
                >
                  {reserving === item.id ? 'Бронируем...' : item.status === 'reserved' ? 'Уже занято' : 'Забронировать'}
                </button>
              </motion.article>
            ))}
          </motion.div>

          <button
            className="ghost"
            onClick={() => shareLink(
              buildStartAppLink(token),
              'Посмотри мою карту желаний \u{1F381}'
            )}
          >
            Поделиться созвездием
          </button>
        </>
      )}

      <AnimatePresence>
        {reserved && (
          <motion.div className="confetti" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            Подарок забронирован!
          </motion.div>
        )}
      </AnimatePresence>
    </Shell>
  );
}

/* ===== Local Wishlist Info ===== */
function LocalWishlistInfo({ onBack }) {
  return (
    <Shell title="Карта желаний" subtitle="Создайте список и делитесь ссылкой" onBack={onBack}>
      <div className="story-card">
        <h3>Как это работает?</h3>
        <p>Создайте список желаний через API и поделитесь ссылкой с друзьями. Они смогут забронировать подарки для вас.</p>
      </div>

      <div className="stack" style={{ gap: 8 }}>
        <p className="section-title">API эндпоинты</p>
        <code>POST /v1/wishlists</code>
        <code>POST /v1/wishlists/{'{id}'}/items</code>
      </div>

      <div className="story-card">
        <p style={{ fontSize: '0.85rem' }}>
          Для открытия публичной витрины используйте параметр <code style={{ display: 'inline', padding: '2px 6px', borderRadius: 6 }}>startapp=wl_...</code>
        </p>
      </div>
    </Shell>
  );
}

/* ===== App Root ===== */
export default function App() {
  const startParam = useStartParam();
  const [view, setView] = useState('dashboard');

  const onboardingDone = useMemo(() => localStorage.getItem('onboarding_complete') === '1', []);
  const [hasOnboarding, setHasOnboarding] = useState(onboardingDone);

  useEffect(() => {
    if (startParam?.startsWith('comp_')) {
      setView('compat');
      return;
    }
    if (startParam?.startsWith('wl_')) {
      setView('wishlist-public');
      return;
    }
    if (!onboardingDone) {
      setView('onboarding');
    }
  }, [startParam, onboardingDone]);

  if (view === 'compat' && startParam?.startsWith('comp_')) {
    return <CompatibilityLanding token={startParam} />;
  }

  if (view === 'wishlist-public' && startParam?.startsWith('wl_')) {
    return <WishlistLanding token={startParam} />;
  }

  if (view === 'onboarding' || !hasOnboarding) {
    return <Onboarding onComplete={() => { setHasOnboarding(true); setView('dashboard'); }} />;
  }

  if (view === 'stories') {
    return <Stories onBack={() => setView('dashboard')} />;
  }

  if (view === 'natal') {
    return <NatalChart onBack={() => setView('dashboard')} />;
  }

  if (view === 'tarot') {
    return <Tarot onBack={() => setView('dashboard')} />;
  }

  if (view === 'wishlist-local') {
    return <LocalWishlistInfo onBack={() => setView('dashboard')} />;
  }

  return (
    <Dashboard
      onOpenNatal={() => setView('natal')}
      onOpenStories={() => setView('stories')}
      onOpenTarot={() => setView('tarot')}
      onOpenWishlist={() => setView('wishlist-local')}
      onResetOnboarding={() => {
        localStorage.removeItem('onboarding_complete');
        setHasOnboarding(false);
        setView('onboarding');
      }}
    />
  );
}
