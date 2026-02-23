import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useLaunchParams } from '@telegram-apps/sdk-react';

import { apiRequest, pollTask, calculateNumerology, fetchNatalPremium } from './api';

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || 'replace_me_bot';
const APP_NAME = import.meta.env.VITE_APP_NAME || 'app';
const TAROT_LOADING_GIF = import.meta.env.VITE_TAROT_LOADING_GIF || '/tarot-loader.gif';
const NATAL_LOADING_GIF = import.meta.env.VITE_NATAL_LOADING_GIF || '/natal-loader.gif';

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

const VIEW_TELEMETRY_EVENTS = {
  natal: 'open_natal_screen',
  stories: 'open_stories_screen',
  tarot: 'open_tarot_screen',
  numerology: 'open_numerology_screen'
};

const NUMEROLOGY_LOADING_HINTS = [
  'Числа раскрывают тайный код твоей судьбы...',
  'Пифагор знал: каждая цифра — вибрация вселенной...',
  'Имя и дата складываются в уникальный узор...',
  'Мастер-числа требуют особого внимания...',
  'Интерпретация почти готова...'
];

const NUMEROLOGY_ARCHETYPES = {
  1: 'Лидер', 2: 'Дипломат', 3: 'Творец', 4: 'Строитель',
  5: 'Авантюрист', 6: 'Гармонизатор', 7: 'Мистик', 8: 'Властелин',
  9: 'Мудрец', 11: 'Интуит', 22: 'Великий Строитель', 33: 'Учитель'
};

const NUMEROLOGY_GRADIENTS = {
  1: 'linear-gradient(135deg, #FF6B35 0%, #FFD700 100%)',
  2: 'linear-gradient(135deg, #C0C0C0 0%, #4A90D9 100%)',
  3: 'linear-gradient(135deg, #FFD700 0%, #FF8C00 100%)',
  4: 'linear-gradient(135deg, #228B22 0%, #8B6914 100%)',
  5: 'linear-gradient(135deg, #40E0D0 0%, #9B59B6 100%)',
  6: 'linear-gradient(135deg, #FF69B4 0%, #FFD700 100%)',
  7: 'linear-gradient(135deg, #4B0082 0%, #8B00FF 100%)',
  8: 'linear-gradient(135deg, #1a1a1a 0%, #FFD700 100%)',
  9: 'linear-gradient(135deg, #DC143C 0%, #F5F5F5 100%)',
  11: 'linear-gradient(135deg, #FF6B6B 0%, #FFE66D 30%, #A8E6CF 60%, #88D8B0 100%)',
  22: 'linear-gradient(135deg, #1a237e 0%, #283593 50%, #FFD700 100%)',
  33: 'linear-gradient(135deg, #880E4F 0%, #AD1457 50%, #F8BBD0 100%)'
};

const NUMEROLOGY_LABELS = {
  life_path: 'Число Жизненного Пути',
  expression: 'Число Выражения',
  soul_urge: 'Число Души',
  personality: 'Число Личности',
  birthday: 'Число Дня Рождения',
  personal_year: 'Число Личного Года'
};

const NUMEROLOGY_ORDER = ['life_path', 'expression', 'soul_urge', 'personality', 'birthday', 'personal_year'];

const NATAL_LOADING_HINTS = [
  'Сверяем дыхание Луны и линию твоего рождения...',
  'Дом за домом карта проступает из звёздной пыли...',
  'Планеты занимают свои места, дождись завершения круга...',
  'Тонкие аспекты уже сплетаются в единый узор...',
  'Ещё немного — послание карты почти готово...'
];

const PREMIUM_NATAL_LOADING_HINTS = [
  'Gemini изучает тонкие аспекты вашей карты...',
  'Глубинный анализ Солнца, Луны и Асцендента...',
  'Рассчитываем ключевые темы всех сфер жизни...',
  'Формируем сильные стороны и персональные вызовы...',
  'Финальный штрих — рекомендации почти готовы...'
];

const LIFE_THEME_ICONS = { career: '💼', love: '❤️', finance: '💰', health: '🌿', growth: '🌱' };
const LIFE_THEME_LABELS = {
  career: 'Карьера и призвание',
  love: 'Отношения и любовь',
  finance: 'Финансы и ресурсы',
  health: 'Здоровье и тело',
  growth: 'Личностный рост'
};
const CORE_ICONS = { sun: '☀️', moon: '🌙', rising: '↑' };
const CORE_LABELS = { sun: 'Солнце', moon: 'Луна', rising: 'Асцендент' };
const STORY_SLIDE_DURATION_MS = 7200;

function storyCardMotion(animationType) {
  const mapping = {
    glow: {
      initial: { opacity: 0, scale: 0.96, filter: 'blur(5px)' },
      animate: { opacity: 1, scale: 1, filter: 'blur(0px)' },
      exit: { opacity: 0, scale: 1.02, filter: 'blur(5px)' },
      transition: { duration: 0.34, ease: [0.22, 1, 0.36, 1] }
    },
    pulse: {
      initial: { opacity: 0, y: 18, scale: 0.98 },
      animate: { opacity: 1, y: 0, scale: 1 },
      exit: { opacity: 0, y: -12, scale: 0.98 },
      transition: { duration: 0.28, ease: 'easeOut' }
    },
    float: {
      initial: { opacity: 0, y: 22, rotate: -0.8 },
      animate: { opacity: 1, y: 0, rotate: 0 },
      exit: { opacity: 0, y: -14, rotate: 0.8 },
      transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] }
    },
    orbit: {
      initial: { opacity: 0, x: 20, scale: 0.96 },
      animate: { opacity: 1, x: 0, scale: 1 },
      exit: { opacity: 0, x: -16, scale: 0.98 },
      transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] }
    }
  };
  return mapping[animationType] || mapping.glow;
}

function toNumber(value) {
  if (typeof value !== 'string') return Number(value);
  return Number(value.replace(',', '.').trim());
}

function timezoneLabel(timezone) {
  if (!timezone) return 'UTC';
  return TZ_LABELS[timezone] || timezone.replaceAll('_', ' ');
}

function browserTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow';
}

function defaultBirthForm() {
  return {
    birth_date: '',
    birth_time: '12:00',
    birth_place: '',
    latitude: '',
    longitude: '',
    timezone: browserTimezone()
  };
}

function toTimeInputValue(rawValue) {
  if (!rawValue) return '12:00';
  const source = String(rawValue).trim();
  if (!source) return '12:00';
  const parts = source.split(':');
  if (parts.length >= 2) {
    const hh = String(parts[0]).padStart(2, '0').slice(0, 2);
    const mm = String(parts[1]).padStart(2, '0').slice(0, 2);
    return `${hh}:${mm}`;
  }
  return '12:00';
}

function profileToBirthForm(profile) {
  return {
    birth_date: String(profile?.birth_date || ''),
    birth_time: toTimeInputValue(profile?.birth_time),
    birth_place: String(profile?.birth_place || ''),
    latitude: profile?.latitude != null ? String(profile.latitude) : '',
    longitude: profile?.longitude != null ? String(profile.longitude) : '',
    timezone: String(profile?.timezone || browserTimezone())
  };
}

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
  // Hook must be called unconditionally at the top level (Rules of Hooks)
  const launchParams = useLaunchParams();
  let sdkStartParam = null;
  try {
    sdkStartParam = launchParams?.startParam ?? null;
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
    sc_tarot: 'tarot',
    sc_numerology: 'numerology'
  };
  return mapping[startParam] || null;
}

function isMissingProfileError(error) {
  const status = Number(error?.status);
  if (status === 404) return true;

  const message = String(error?.message || error || '').toLowerCase();
  return (
    message.includes('not found')
    || message.includes('не найден')
    || message.includes('не найдена')
  );
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
      <span
        className="hint-icon"
        role="button"
        aria-label="Подсказка"
        aria-expanded={show}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setShow(!show)}
      >?</span>
      {show && <span className="hint-text" role="tooltip">{text}</span>}
    </span>
  );
}

function Shell({ title, subtitle, children, onBack, className = '' }) {
  return (
    <motion.div role="main" className={`screen ${className}`.trim()} variants={pageVariants} initial="initial" animate="animate" exit="exit">
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
    </motion.div>
  );
}

function Onboarding({ mode = 'create', onComplete, onBack }) {
  const isEditMode = mode === 'edit';
  // Multi-step state: 0=Welcome, 1=DateTime, 2=Place, 3=Review (skip Welcome in edit mode)
  const [currentStep, setCurrentStep] = useState(isEditMode ? 1 : 0);
  const [loading, setLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(isEditMode);
  const [error, setError] = useState('');
  const [profileMessage, setProfileMessage] = useState('');
  const [profileMessageType, setProfileMessageType] = useState('info');
  const [form, setForm] = useState(() => defaultBirthForm());

  const [citySuggestions, setCitySuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [citySearchStatus, setCitySearchStatus] = useState('idle');
  const [citySelected, setCitySelected] = useState(false);
  const [showManualCoords, setShowManualCoords] = useState(false);
  const cityDebounceRef = useRef(null);
  const timezoneDebounceRef = useRef(null);
  const cityRequestRef = useRef(0);
  const wrapperRef = useRef(null);

  const searchCities = useCallback((query) => {
    const normalizedQuery = query.trim();
    if (cityDebounceRef.current) clearTimeout(cityDebounceRef.current);
    if (normalizedQuery.length < 1) {
      setCitySuggestions([]);
      setShowSuggestions(false);
      setCitySearchStatus('idle');
      return;
    }

    setCitySearchStatus('loading');
    cityDebounceRef.current = setTimeout(async () => {
      const requestId = cityRequestRef.current + 1;
      cityRequestRef.current = requestId;
      try {
        const results = await apiRequest(`/v1/geo/cities?q=${encodeURIComponent(normalizedQuery)}`);
        if (requestId !== cityRequestRef.current) return;
        setCitySuggestions(results);
        const hasResults = results.length > 0;
        setShowSuggestions(hasResults);
        setCitySearchStatus(hasResults ? 'found' : 'not_found');
        if (!hasResults) setShowManualCoords(true);
      } catch {
        if (requestId !== cityRequestRef.current) return;
        setCitySuggestions([]);
        setShowSuggestions(false);
        setCitySearchStatus('error');
      }
    }, 300);
  }, []);

  const handleCityInput = (value) => {
    setProfileMessage('');
    setForm((prev) => ({ ...prev, birth_place: value, latitude: '', longitude: '' }));
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
    setCitySearchStatus('found');
    setShowManualCoords(false);
    setShowSuggestions(false);
    setCitySuggestions([]);
  };

  const setLatitude = (value) => {
    setProfileMessage('');
    setCitySelected(false);
    setShowManualCoords(true);
    setForm((prev) => ({ ...prev, latitude: value }));
  };

  const setLongitude = (value) => {
    setProfileMessage('');
    setCitySelected(false);
    setShowManualCoords(true);
    setForm((prev) => ({ ...prev, longitude: value }));
  };

  useEffect(() => {
    if (!isEditMode) {
      setLoadingProfile(false);
      setProfileMessage('');
      return undefined;
    }

    let active = true;
    setLoadingProfile(true);
    setError('');
    setProfileMessage('');

    apiRequest('/v1/natal/profile/latest')
      .then((profile) => {
        if (!active) return;
        setForm(profileToBirthForm(profile));
        setCitySelected(true);
        setShowManualCoords(false);
        setCitySearchStatus('idle');
        setCitySuggestions([]);
        setShowSuggestions(false);
        setProfileMessage('Текущие данные загружены из профиля. Измените нужные поля и сохраните.');
        setProfileMessageType('ok');
      })
      .catch((e) => {
        if (!active) return;
        const rawMessage = String(e?.message || e || '');
        const lowered = rawMessage.toLowerCase();
        if (lowered.includes('not found') || lowered.includes('404')) {
          setProfileMessage('Сохранённые данные не найдены. Заполните форму и сохраните.');
        } else {
          setProfileMessage(
            rawMessage || 'Не удалось загрузить сохранённые данные. Заполните форму вручную.'
          );
        }
        setProfileMessageType('warning');
      })
      .finally(() => {
        if (active) setLoadingProfile(false);
      });

    return () => {
      active = false;
    };
  }, [isEditMode]);

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

  useEffect(() => {
    if (timezoneDebounceRef.current) clearTimeout(timezoneDebounceRef.current);
    const lat = toNumber(form.latitude);
    const lon = toNumber(form.longitude);
    const hasValidCoords = Number.isFinite(lat)
      && Number.isFinite(lon)
      && lat >= -90
      && lat <= 90
      && lon >= -180
      && lon <= 180;

    if (!hasValidCoords || citySelected) return;

    timezoneDebounceRef.current = setTimeout(async () => {
      try {
        const tzResult = await apiRequest(`/v1/geo/timezone?latitude=${lat}&longitude=${lon}`);
        setForm((prev) => ({ ...prev, timezone: tzResult.timezone || 'UTC' }));
      } catch {
        // ignore and keep the timezone selected by user/browser
      }
    }, 350);

    return () => {
      if (timezoneDebounceRef.current) clearTimeout(timezoneDebounceRef.current);
    };
  }, [form.latitude, form.longitude, citySelected]);

  const timezoneOptions = useMemo(() => {
    if (!form.timezone || TIMEZONES.includes(form.timezone)) return TIMEZONES;
    return [form.timezone, ...TIMEZONES];
  }, [form.timezone]);

  const latitude = toNumber(form.latitude);
  const longitude = toNumber(form.longitude);
  const hasValidCoordinates = Number.isFinite(latitude)
    && Number.isFinite(longitude)
    && latitude >= -90
    && latitude <= 90
    && longitude >= -180
    && longitude <= 180;

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
          latitude: latitude,
          longitude: longitude,
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

  // Step navigation
  const totalSteps = isEditMode ? 3 : 4;
  const progress = ((currentStep + (isEditMode ? 0 : 1)) / totalSteps) * 100;

  const canProceedStep1 = form.birth_date && form.birth_time;
  const canProceedStep2 = form.birth_place && hasValidCoordinates && form.timezone;
  const canSubmit = canProceedStep1 && canProceedStep2;

  const nextStep = () => {
    if (currentStep === 0) setCurrentStep(1);
    else if (currentStep === 1 && canProceedStep1) setCurrentStep(2);
    else if (currentStep === 2 && canProceedStep2) setCurrentStep(3);
  };

  const prevStep = () => {
    if (currentStep > (isEditMode ? 1 : 0)) {
      setCurrentStep(currentStep - 1);
      setError('');
    }
  };

  const handleBack = () => {
    if (isEditMode && currentStep === 1) {
      onBack();
    } else {
      prevStep();
    }
  };

  const title = isEditMode ? 'Данные рождения' :
    currentStep === 0 ? 'Добро пожаловать' :
    currentStep === 1 ? 'Дата и время' :
    currentStep === 2 ? 'Место рождения' :
    'Проверка данных';

  const subtitle = isEditMode
    ? 'Проверьте и обновите профиль. Изменения применятся только после сохранения.'
    : currentStep === 0 ? 'Начнём ваше звёздное путешествие' :
      currentStep === 1 ? 'Когда вы появились на свет?' :
      currentStep === 2 ? 'Где прошёл ваш первый вдох?' :
      'Всё готово к созданию карты';

  const submitTitle = loading
    ? (isEditMode ? 'Сохраняем изменения...' : 'Считаем карту...')
    : (isEditMode ? 'Сохранить изменения' : 'Создать мою карту');

  return (
    <Shell
      title={title}
      subtitle={subtitle}
      onBack={currentStep > (isEditMode ? 1 : 0) || isEditMode ? handleBack : undefined}
    >
      {/* Progress Bar */}
      {!isEditMode && (
        <motion.div
          style={{
            height: '4px',
            background: 'var(--gradient-mystical)',
            borderRadius: 'var(--radius-full)',
            transformOrigin: 'left',
            marginBottom: 'var(--spacing-3)',
            width: `${progress}%`,
            transition: 'width 0.4s cubic-bezier(0.4, 0.0, 0.2, 1)'
          }}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
        />
      )}

      <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate" key={currentStep}>

        {/* STEP 0: WELCOME HERO (only in create mode) */}
        {!isEditMode && currentStep === 0 && (
          <>
            <motion.article className="onboarding-intro" variants={staggerItem}>
              <div style={{ textAlign: 'center', padding: 'var(--spacing-3) 0' }}>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
                  style={{ fontSize: '64px', marginBottom: 'var(--spacing-2)' }}
                >
                  ✨
                </motion.div>
                <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '28px' }}>
                  Ваша звёздная карта
                </h2>
                <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--spacing-3)' }}>
                  Откройте тайны вашего рождения через призму космоса
                </p>
              </div>
              <div className="onboarding-points">
                <span>🌙 Натальная карта</span>
                <span>🔮 Персональные прогнозы</span>
                <span>💫 Совместимость</span>
              </div>
            </motion.article>
            <motion.button
              className="cta"
              onClick={nextStep}
              variants={staggerItem}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
            >
              Начать путешествие
            </motion.button>
          </>
        )}

        {/* STEP 1: BIRTH DATE & TIME (create mode only; edit mode has its own combined block) */}
        {!isEditMode && currentStep === 1 && (
          <>
            {!isEditMode && (
              <motion.article className="onboarding-intro" variants={staggerItem}>
                <p className="section-title">Шаг 1 из 3</p>
                <p>Эти данные нужны для точного расчёта натальной карты и персональных прогнозов.</p>
              </motion.article>
            )}

            {loadingProfile && (
              <motion.div className="onboarding-message" variants={staggerItem}>
                Загружаем сохранённые данные...
              </motion.div>
            )}

            {profileMessage && !loadingProfile && (
              <motion.div
                className={`onboarding-message ${profileMessageType === 'warning' ? 'warning' : 'ok'}`}
                variants={staggerItem}
              >
                {profileMessage}
              </motion.div>
            )}

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

            {!isEditMode && (
              <motion.button
                className="cta"
                onClick={nextStep}
                disabled={!canProceedStep1}
                variants={staggerItem}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.96 }}
              >
                Далее
              </motion.button>
            )}
          </>
        )}

        {/* STEP 2: BIRTH PLACE (create mode only) */}
        {!isEditMode && currentStep === 2 && (
          <>
            {!isEditMode && (
              <motion.article className="onboarding-intro" variants={staggerItem}>
                <p className="section-title">Шаг 2 из 3</p>
                <p>Место рождения нужно для определения координат и часового пояса.</p>
              </motion.article>
            )}

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
                          <span className="city-tz">{timezoneLabel(city.timezone)}</span>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>

                {citySearchStatus === 'loading' && (
                  <span className="input-hint">Ищем город...</span>
                )}
                {citySearchStatus === 'error' && (
                  <span className="input-hint city-warning-hint">Поиск временно недоступен. Можно указать координаты вручную.</span>
                )}
                {citySearchStatus === 'not_found' && (
                  <motion.div className="city-status city-status-warning" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <p>Такой город не найден. Продолжайте по координатам.</p>
                  </motion.div>
                )}
                {citySelected && (
                  <span className="input-hint city-success-hint">
                    Координаты и часовой пояс заполнены автоматически
                  </span>
                )}
              </div>
            </motion.div>

            <motion.div variants={staggerItem}>
              <label>
                Часовой пояс
                <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
                  {timezoneOptions.map((tz) => (
                    <option key={tz} value={tz}>{timezoneLabel(tz)}</option>
                  ))}
                </select>
                <span className="input-hint">Текущий пояс: {timezoneLabel(form.timezone)}</span>
              </label>
            </motion.div>

            {!showManualCoords && !citySelected && form.birth_place && citySearchStatus !== 'not_found' && (
              <motion.div variants={staggerItem}>
                <button className="profile-toggle" onClick={() => setShowManualCoords(true)} type="button">
                  Нет моего города? Указать координаты вручную
                </button>
              </motion.div>
            )}

            {(showManualCoords || (!citySelected && form.latitude)) && (
              <motion.div variants={staggerItem} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                <p className="input-hint coords-help">
                  Можно ввести координаты вручную, например: 55.7558 и 37.6173. Часовой пояс обновится автоматически.
                </p>
                <div className="grid-2">
                  <label>
                    Широта
                    <input
                      placeholder="55.7558"
                      value={form.latitude}
                      onChange={(e) => setLatitude(e.target.value)}
                      inputMode="decimal"
                    />
                  </label>
                  <label>
                    Долгота
                    <input
                      placeholder="37.6173"
                      value={form.longitude}
                      onChange={(e) => setLongitude(e.target.value)}
                      inputMode="decimal"
                    />
                  </label>
                </div>
                {!hasValidCoordinates && form.latitude && form.longitude && (
                  <span className="input-hint city-warning-hint">Проверьте координаты: широта от -90 до 90, долгота от -180 до 180.</span>
                )}
              </motion.div>
            )}

            {!isEditMode && (
              <motion.button
                className="cta"
                onClick={nextStep}
                disabled={!canProceedStep2}
                variants={staggerItem}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.96 }}
              >
                Далее
              </motion.button>
            )}
          </>
        )}

        {/* STEP 3: REVIEW & SUBMIT (only in create mode) */}
        {!isEditMode && currentStep === 3 && (
          <>
            <motion.article className="onboarding-intro" variants={staggerItem}>
              <p className="section-title">Шаг 3 из 3</p>
              <p>Проверьте данные перед созданием карты</p>
            </motion.article>

            <motion.div className="glass-card" variants={staggerItem}>
              <h3 style={{ marginBottom: 'var(--spacing-2)' }}>Ваши данные</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                <div>
                  <small>Дата и время рождения</small>
                  <p style={{ color: 'var(--text)', marginTop: '4px' }}>
                    {form.birth_date} в {form.birth_time}
                  </p>
                </div>
                <div>
                  <small>Место рождения</small>
                  <p style={{ color: 'var(--text)', marginTop: '4px' }}>
                    {form.birth_place}
                  </p>
                  <p style={{ fontSize: '13px', marginTop: '4px' }}>
                    {latitude.toFixed(4)}, {longitude.toFixed(4)}
                  </p>
                </div>
                <div>
                  <small>Часовой пояс</small>
                  <p style={{ color: 'var(--text)', marginTop: '4px' }}>
                    {timezoneLabel(form.timezone)}
                  </p>
                </div>
              </div>
            </motion.div>

            <motion.button
              className="cta"
              onClick={submit}
              disabled={loading || !canSubmit}
              variants={staggerItem}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
            >
              {submitTitle}
            </motion.button>
          </>
        )}

        {/* EDIT MODE: ALL FIELDS */}
        {isEditMode && currentStep === 1 && (
          <>
            {loadingProfile && (
              <motion.div className="onboarding-message" variants={staggerItem}>
                Загружаем сохранённые данные...
              </motion.div>
            )}

            {profileMessage && !loadingProfile && (
              <motion.div
                className={`onboarding-message ${profileMessageType === 'warning' ? 'warning' : 'ok'}`}
                variants={staggerItem}
              >
                {profileMessage}
              </motion.div>
            )}

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
                          <span className="city-tz">{timezoneLabel(city.timezone)}</span>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>

                {citySearchStatus === 'loading' && (
                  <span className="input-hint">Ищем город...</span>
                )}
                {citySearchStatus === 'error' && (
                  <span className="input-hint city-warning-hint">Поиск временно недоступен. Можно указать координаты вручную.</span>
                )}
                {citySearchStatus === 'not_found' && (
                  <motion.div className="city-status city-status-warning" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <p>Такой город не найден. Продолжайте по координатам.</p>
                  </motion.div>
                )}
                {citySelected && (
                  <span className="input-hint city-success-hint">
                    Координаты и часовой пояс заполнены автоматически
                  </span>
                )}
              </div>
            </motion.div>

            <motion.div variants={staggerItem}>
              <label>
                Часовой пояс
                <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
                  {timezoneOptions.map((tz) => (
                    <option key={tz} value={tz}>{timezoneLabel(tz)}</option>
                  ))}
                </select>
                <span className="input-hint">Текущий пояс: {timezoneLabel(form.timezone)}</span>
              </label>
            </motion.div>

            {!showManualCoords && !citySelected && form.birth_place && citySearchStatus !== 'not_found' && (
              <motion.div variants={staggerItem}>
                <button className="profile-toggle" onClick={() => setShowManualCoords(true)} type="button">
                  Нет моего города? Указать координаты вручную
                </button>
              </motion.div>
            )}

            {(showManualCoords || (!citySelected && form.latitude)) && (
              <motion.div variants={staggerItem} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                <p className="input-hint coords-help">
                  Можно ввести координаты вручную, например: 55.7558 и 37.6173. Часовой пояс обновится автоматически.
                </p>
                <div className="grid-2">
                  <label>
                    Широта
                    <input
                      placeholder="55.7558"
                      value={form.latitude}
                      onChange={(e) => setLatitude(e.target.value)}
                      inputMode="decimal"
                    />
                  </label>
                  <label>
                    Долгота
                    <input
                      placeholder="37.6173"
                      value={form.longitude}
                      onChange={(e) => setLongitude(e.target.value)}
                      inputMode="decimal"
                    />
                  </label>
                </div>
                {!hasValidCoordinates && form.latitude && form.longitude && (
                  <span className="input-hint city-warning-hint">Проверьте координаты: широта от -90 до 90, долгота от -180 до 180.</span>
                )}
              </motion.div>
            )}

            <motion.div variants={staggerItem} className="grid-2 onboarding-actions">
              <button className="ghost" type="button" onClick={onBack} disabled={loading}>
                Назад
              </button>
              <button className="cta" onClick={submit} disabled={loading || loadingProfile || !canSubmit}>
                {submitTitle}
              </button>
            </motion.div>
          </>
        )}

        {/* ERROR MESSAGE */}
        {error && (
          <motion.p className="error" role="alert" aria-live="polite" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {error}
          </motion.p>
        )}
      </motion.div>
    </Shell>
  );
}

function NumerologyCard({ numberKey, value, interpretation, interpretationLoading }) {
  const gradient = NUMEROLOGY_GRADIENTS[value] || NUMEROLOGY_GRADIENTS[9];
  const archetype = NUMEROLOGY_ARCHETYPES[value] || '';
  const label = NUMEROLOGY_LABELS[numberKey] || numberKey;
  const isMaster = value === 11 || value === 22 || value === 33;

  return (
    <motion.article
      className="numerology-card"
      variants={staggerItem}
      style={{ '--num-gradient': gradient }}
    >
      <div className="numerology-card-header">
        <div className="numerology-number-circle" style={{ background: gradient }}>
          <motion.span
            className="numerology-big-number"
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            {value}
          </motion.span>
        </div>
        <div className="numerology-card-titles">
          <p className="numerology-label">{label}</p>
          <p className="numerology-archetype">{archetype}</p>
          {isMaster && (
            <span className="numerology-master-badge">✦ Мастер-число</span>
          )}
        </div>
      </div>

      <div className="numerology-interpretation">
        {interpretationLoading ? (
          <motion.p
            className="numerology-interp-loading"
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          >
            Толкование загружается...
          </motion.p>
        ) : interpretation ? (
          <p>{interpretation}</p>
        ) : (
          <p className="numerology-interp-placeholder">Интерпретация временно недоступна.</p>
        )}
      </div>
    </motion.article>
  );
}

function Numerology({ onBack, onMissingProfile }) {
  const [step, setStep] = useState(0);
  const [nameInput, setNameInput] = useState('');
  const [birthDateInput, setBirthDateInput] = useState('');
  const [profileLoading, setProfileLoading] = useState(true);
  const [numbers, setNumbers] = useState(null);
  const [interpretations, setInterpretations] = useState(null);
  const [interpretationLoading, setInterpretationLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [error, setError] = useState('');
  const [hintIndex, setHintIndex] = useState(0);

  useEffect(() => {
    let active = true;
    setProfileLoading(true);
    apiRequest('/v1/natal/profile/latest')
      .then((profile) => {
        if (!active) return;
        if (profile?.birth_date) {
          setBirthDateInput(String(profile.birth_date));
        }
      })
      .catch(() => {})
      .finally(() => { if (active) setProfileLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!interpretationLoading) return undefined;
    const id = setInterval(() => {
      setHintIndex((prev) => (prev + 1) % NUMEROLOGY_LOADING_HINTS.length);
    }, 2600);
    return () => clearInterval(id);
  }, [interpretationLoading]);

  const canSubmit = nameInput.trim().length >= 2 && birthDateInput.length === 10;

  const handleCalculate = async () => {
    if (!canSubmit) return;
    setError('');
    setSubmitLoading(true);
    setNumbers(null);
    setInterpretations(null);

    try {
      const data = await calculateNumerology(nameInput.trim(), birthDateInput);
      setNumbers(data.numbers);
      setStep(1);

      if (data.task_id) {
        setInterpretationLoading(true);
        pollTask(data.task_id)
          .then((taskResult) => { setInterpretations(taskResult?.interpretations || null); })
          .catch(() => { setInterpretations(null); })
          .finally(() => { setInterpretationLoading(false); });
      }
    } catch (e) {
      if (isMissingProfileError(e)) { onMissingProfile?.(); return; }
      setError(String(e?.message || e || 'Не удалось рассчитать числа.'));
    } finally {
      setSubmitLoading(false);
    }
  };

  if (step === 0) {
    return (
      <Shell title="Нумерология" subtitle="Числа раскрывают код вашей судьбы" onBack={onBack}>
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
          <motion.article className="glass-card" variants={staggerItem} style={{ padding: 'var(--spacing-3)' }}>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
              Введите полное имя при рождении (как в документах) и дату рождения для расчёта шести ключевых чисел.
            </p>
          </motion.article>

          <motion.div variants={staggerItem}>
            <label>
              Полное имя при рождении
              <Hint text="Имя, фамилия и отчество (при наличии) как в документах" />
              <input
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                placeholder="Иванов Иван Иванович"
                autoComplete="name"
              />
              <span className="input-hint">Кириллица или латиница</span>
            </label>
          </motion.div>

          <motion.div variants={staggerItem}>
            <label>
              Дата рождения
              <Hint text="Если дата загружена из профиля, при необходимости исправьте" />
              {profileLoading ? (
                <span className="input-hint">Загружаем из профиля...</span>
              ) : (
                <input
                  type="date"
                  value={birthDateInput}
                  onChange={(e) => setBirthDateInput(e.target.value)}
                />
              )}
            </label>
          </motion.div>

          {error && (
            <motion.p className="error" role="alert" aria-live="polite" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {error}
            </motion.p>
          )}

          <motion.button
            className="cta"
            onClick={handleCalculate}
            disabled={submitLoading || profileLoading || !canSubmit}
            variants={staggerItem}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.96 }}
          >
            {submitLoading ? 'Считаем числа...' : 'Рассчитать нумерологию'}
          </motion.button>
        </motion.div>
      </Shell>
    );
  }

  return (
    <Shell title="Нумерология" subtitle={`Числовой код: ${nameInput.trim()}`} onBack={() => setStep(0)}>
      <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
        {interpretationLoading && (
          <motion.div
            className="numerology-interp-banner"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <AnimatePresence mode="wait">
              <motion.span
                key={hintIndex}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {NUMEROLOGY_LOADING_HINTS[hintIndex]}
              </motion.span>
            </AnimatePresence>
          </motion.div>
        )}

        {numbers && NUMEROLOGY_ORDER.map((key) => (
          <NumerologyCard
            key={key}
            numberKey={key}
            value={numbers[key]}
            interpretation={interpretations?.[key] || null}
            interpretationLoading={interpretationLoading}
          />
        ))}

        <motion.button
          className="ghost"
          onClick={() => setStep(0)}
          variants={staggerItem}
        >
          Рассчитать заново
        </motion.button>
      </motion.div>
    </Shell>
  );
}

function Dashboard({
  onOpenNatal,
  onOpenStories,
  onOpenTarot,
  onOpenNumerology,
  onEditBirthData,
  onDeleteProfile,
  deletingProfile
}) {
  const menuItems = [
    { icon: '✨', label: 'Натальная карта', hint: 'Полный персональный разбор', action: onOpenNatal },
    { icon: '🌙', label: 'Сторис дня', hint: 'Короткие персональные инсайты', action: onOpenStories },
    { icon: '🃏', label: 'Таро-расклад', hint: 'Карты с пояснениями и анимацией', action: onOpenTarot },
    { icon: '🔢', label: 'Нумерология', hint: 'Числовой код судьбы и личности', action: onOpenNumerology }
  ];

  const [dailyForecast, setDailyForecast] = useState(null);
  const [dailyLoading, setDailyLoading] = useState(true);
  const [dailyError, setDailyError] = useState('');

  useEffect(() => {
    apiRequest('/v1/forecast/daily')
      .then((data) => setDailyForecast(data))
      .catch(() => setDailyError('Не удалось загрузить данные дня'))
      .finally(() => setDailyLoading(false));
  }, []);

  const todayEnergy = dailyForecast?.energy_score ?? null;
  const todayMood = dailyForecast?.payload?.mood ?? null;
  const todayFocus = dailyForecast?.payload?.focus ?? null;

  return (
    <Shell title="Созвездие" subtitle="Астрология и таро в одном потоке.">
      <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">

        {/* HERO CARD: Daily Energy */}
        <motion.div
          className="glass-card"
          variants={staggerItem}
          style={{
            background: 'var(--glass-light)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--spacing-3)',
            position: 'relative',
            overflow: 'hidden'
          }}
        >
          {/* Gradient overlay */}
          <div style={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: '200px',
            height: '200px',
            background: 'radial-gradient(circle at center, rgba(94, 92, 230, 0.2), transparent 70%)',
            pointerEvents: 'none'
          }} />

          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-3)' }}>
              <div>
                <h2 style={{ fontSize: '22px', marginBottom: 'var(--spacing-1)' }}>
                  Сегодня
                </h2>
                <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>
                  {new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
                </p>
              </div>

              {/* Energy circle */}
              <div style={{
                width: '72px',
                height: '72px',
                borderRadius: '50%',
                border: '3px solid var(--glass-medium)',
                background: 'var(--glass-light)',
                backdropFilter: 'var(--blur-strong)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative'
              }}>
                {todayEnergy !== null && (
                  <div style={{
                    position: 'absolute',
                    inset: '-3px',
                    borderRadius: '50%',
                    background: `conic-gradient(var(--accent-vibrant) 0% ${todayEnergy}%, transparent ${todayEnergy}% 100%)`,
                    mask: 'radial-gradient(circle, transparent 32px, black 33px, black 36px, transparent 37px)',
                    WebkitMask: 'radial-gradient(circle, transparent 32px, black 33px, black 36px, transparent 37px)'
                  }} />
                )}
                <span style={{
                  fontSize: dailyLoading ? '14px' : '20px',
                  fontWeight: '700',
                  background: 'var(--gradient-mystical)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text'
                }}>
                  {dailyLoading ? '···' : (todayEnergy ?? '—')}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '-2px' }}>
                  energy
                </span>
              </div>
            </div>

            {/* Insights */}
            {dailyError && (
              <p style={{ fontSize: '13px', color: 'var(--text-tertiary)', margin: 0 }}>{dailyError}</p>
            )}
            {!dailyError && (
            <div style={{ display: 'flex', gap: 'var(--spacing-1)', flexWrap: 'wrap' }}>
              <span style={{
                background: 'var(--accent-glow)',
                border: '1px solid var(--accent)',
                borderRadius: 'var(--radius-full)',
                padding: 'var(--spacing-1) var(--spacing-2)',
                fontSize: '13px',
                fontWeight: '600',
                backdropFilter: 'var(--blur-light)',
                opacity: dailyLoading ? 0.5 : 1
              }}>
                💫 {dailyLoading ? '···' : (todayMood ?? '—')}
              </span>
              <span style={{
                background: 'rgba(191, 90, 242, 0.15)',
                border: '1px solid var(--accent-vibrant)',
                borderRadius: 'var(--radius-full)',
                padding: 'var(--spacing-1) var(--spacing-2)',
                fontSize: '13px',
                fontWeight: '600',
                backdropFilter: 'var(--blur-light)',
                opacity: dailyLoading ? 0.5 : 1
              }}>
                ✨ {dailyLoading ? '···' : (todayFocus ? `в ${todayFocus}` : '—')}
              </span>
            </div>
            )}
          </div>
        </motion.div>

        {/* MENU ITEMS */}
        <div className="card-grid">
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
        </div>

        <button className="profile-toggle" onClick={onEditBirthData}>Изменить данные рождения</button>
        <button className="profile-toggle danger" onClick={onDeleteProfile} disabled={deletingProfile}>
          {deletingProfile ? 'Удаляем профиль...' : 'Удалить профиль'}
        </button>
      </motion.div>
    </Shell>
  );
}

function NatalChart({ onBack, onMissingProfile }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chart, setChart] = useState(null);
  const [hintIndex, setHintIndex] = useState(0);
  const [natalGifFailed, setNatalGifFailed] = useState(false);
  const [natalGifFallbackTried, setNatalGifFallbackTried] = useState(false);

  const natalLoaderSrc = natalGifFallbackTried ? TAROT_LOADING_GIF : NATAL_LOADING_GIF;

  const loadChart = useCallback(async () => {
    setLoading(true);
    setError('');
    setChart(null);
    setHintIndex(0);

    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        let data = await apiRequest('/v1/natal/full');
        // Handle ARQ async path: server returns {status:"pending", task_id:"..."}
        if (data?.status === 'pending' && data?.task_id) {
          data = await pollTask(data.task_id);
        }
        setChart(data);
        setLoading(false);
        return;
      } catch (e) {
        if (attempt < 3) {
          await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
          continue;
        }
        const rawMessage = String(e?.message || e || '');
        const lowered = rawMessage.toLowerCase();
        if (isMissingProfileError(e)) {
          onMissingProfile?.();
          setLoading(false);
          return;
        }
        setError(
          lowered.includes('load failed')
            ? 'Не удалось загрузить натальную карту. Проверьте соединение и попробуйте снова.'
            : (rawMessage || 'Не удалось загрузить натальную карту.')
        );
      }
    }
    setLoading(false);
  }, [onMissingProfile]);

  useEffect(() => {
    loadChart();
  }, [loadChart]);

  useEffect(() => {
    if (!loading) return undefined;
    const intervalId = setInterval(() => {
      setHintIndex((prev) => (prev + 1) % NATAL_LOADING_HINTS.length);
    }, 2600);
    return () => clearInterval(intervalId);
  }, [loading]);

  return (
    <Shell title="Натальная карта" subtitle="Подробный персональный разбор" onBack={onBack}>
      {loading && (
        <motion.div
          className="natal-loader"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {!natalGifFailed && natalLoaderSrc ? (
            <motion.div
              className="natal-loader-gif-stage"
              initial={{ opacity: 0.6, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.35 }}
            >
              <img
                className="natal-loader-gif"
                src={natalLoaderSrc}
                alt="Natal loading"
                loading="eager"
                onError={() => {
                  if (!natalGifFallbackTried && TAROT_LOADING_GIF && TAROT_LOADING_GIF !== NATAL_LOADING_GIF) {
                    setNatalGifFallbackTried(true);
                    return;
                  }
                  setNatalGifFailed(true);
                }}
              />
            </motion.div>
          ) : (
            <div className="natal-loader-placeholder">🌙</div>
          )}
          <p className="natal-loader-title">Читаем звёздный узор...</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={hintIndex}
              className="natal-loader-hint"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
            >
              {NATAL_LOADING_HINTS[hintIndex]}
            </motion.p>
          </AnimatePresence>
        </motion.div>
      )}

      {error && (
        <div className="stack" role="alert" aria-live="polite">
          <p className="error">{error}</p>
          <button className="ghost" onClick={loadChart}>Повторить загрузку</button>
        </div>
      )}

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

// ── Premium natal: mode selector ────────────────────────────────────

function NatalModeSelect({ onBack, onBasic, onPremium }) {
  const goldBorder = {
    background: 'linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(15,15,20,0.95) 100%)',
    border: '1px solid rgba(245,158,11,0.4)',
    boxShadow: '0 0 24px rgba(245,158,11,0.10), inset 0 1px 0 rgba(245,158,11,0.15)',
    borderRadius: 'var(--radius-xl)',
    padding: 'var(--spacing-3)'
  };
  const featureList = {
    listStyle: 'none',
    padding: 0,
    margin: '8px 0 0',
    display: 'flex',
    flexDirection: 'column',
    gap: 6
  };
  const featureItem = { fontSize: 14, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 };

  return (
    <Shell title="Натальная карта" subtitle="Выберите формат анализа" onBack={onBack}>
      <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">

        {/* Basic option */}
        <motion.div className="glass-card" variants={staggerItem} style={{ borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <span style={{ fontSize: 28 }}>🌙</span>
            <span style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
              color: 'var(--text-tertiary)', background: 'var(--glass-light)',
              border: '1px solid var(--glass-medium)', borderRadius: 20, padding: '3px 10px'
            }}>Бесплатно</span>
          </div>
          <h3 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Базовая карта</h3>
          <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>Расчёт планет и интерпретации от локальной AI-модели</p>
          <ul style={featureList}>
            {['10 планет и домов', 'Ключевые аспекты', 'Базовые интерпретации', 'Локальная AI-модель'].map(f => (
              <li key={f} style={featureItem}><span style={{ color: 'var(--text-tertiary)' }}>•</span>{f}</li>
            ))}
          </ul>
          <motion.button
            className="ghost"
            onClick={onBasic}
            whileTap={{ scale: 0.97 }}
            style={{ width: '100%', marginTop: 16 }}
          >
            Получить бесплатно →
          </motion.button>
        </motion.div>

        {/* Premium option */}
        <motion.div variants={staggerItem} style={goldBorder}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <span style={{ fontSize: 28 }}>⭐</span>
            <span style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
              color: '#F59E0B', background: 'rgba(245,158,11,0.15)',
              border: '1px solid rgba(245,158,11,0.4)', borderRadius: 20, padding: '3px 10px'
            }}>Премиум</span>
          </div>
          <h3 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Детальный отчёт</h3>
          <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>Глубокий персональный анализ от Gemini Flash</p>
          <ul style={featureList}>
            {[
              'Анализ Солнца, Луны и Асцендента',
              '5 сфер жизни: карьера, любовь, финансы...',
              'Сильные стороны и вызовы',
              'Топ-3 значимых аспекта',
              'Персональные рекомендации'
            ].map(f => (
              <li key={f} style={{ ...featureItem, color: 'rgba(245,245,245,0.75)' }}>
                <span style={{ color: 'rgba(245,158,11,0.7)' }}>✦</span>{f}
              </li>
            ))}
          </ul>
          <motion.button
            onClick={onPremium}
            whileTap={{ scale: 0.97 }}
            style={{
              width: '100%', marginTop: 16, padding: '14px 0',
              background: 'linear-gradient(135deg, #D97706 0%, #F59E0B 100%)',
              border: 'none', borderRadius: 'var(--radius-lg)', color: '#000',
              fontSize: 15, fontWeight: 700, cursor: 'pointer', letterSpacing: '0.02em'
            }}
          >
            Получить отчёт ⭐
          </motion.button>
        </motion.div>

      </motion.div>
    </Shell>
  );
}

// ── Premium natal: full report ───────────────────────────────────────

function NatalPremiumReport({ onBack, onMissingProfile }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [hintIndex, setHintIndex] = useState(0);
  const [openCore, setOpenCore] = useState(null);
  const [openTheme, setOpenTheme] = useState('career');

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError('');
    setResult(null);
    setHintIndex(0);
    try {
      const data = await fetchNatalPremium();
      if (!data?.report) {
        setError('Не удалось сформировать отчёт. Попробуйте ещё раз.');
      } else {
        setResult(data);
      }
    } catch (e) {
      if (isMissingProfileError(e)) { onMissingProfile?.(); return; }
      setError(String(e?.message || e || 'Ошибка загрузки отчёта.'));
    } finally {
      setLoading(false);
    }
  }, [onMissingProfile]);

  useEffect(() => { loadReport(); }, [loadReport]);

  useEffect(() => {
    if (!loading) return undefined;
    const id = setInterval(() => setHintIndex(p => (p + 1) % PREMIUM_NATAL_LOADING_HINTS.length), 2600);
    return () => clearInterval(id);
  }, [loading]);

  const report = result?.report;

  // gold design tokens
  const gold = '#F59E0B';
  const goldBg = 'rgba(245,158,11,0.12)';
  const goldBorder = 'rgba(245,158,11,0.35)';

  const sectionTitle = (icon, text) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <span style={{
        fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: gold
      }}>{text}</span>
    </div>
  );

  const divider = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '4px 0' }}>
      <div style={{ flex: 1, height: 1, background: `linear-gradient(to right, transparent, ${goldBorder})` }} />
      <span style={{ color: gold, fontSize: 12 }}>✦</span>
      <div style={{ flex: 1, height: 1, background: `linear-gradient(to left, transparent, ${goldBorder})` }} />
    </div>
  );

  return (
    <Shell title="Детальный отчёт" subtitle="Персональный астрологический анализ" onBack={onBack}>

      {/* Loading */}
      {loading && (
        <motion.div className="natal-loader" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <div className="natal-loader-placeholder" style={{ fontSize: 32 }}>⭐</div>
          <p className="natal-loader-title" style={{ color: gold }}>Gemini анализирует карту...</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={hintIndex} className="natal-loader-hint"
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
            >
              {PREMIUM_NATAL_LOADING_HINTS[hintIndex]}
            </motion.p>
          </AnimatePresence>
        </motion.div>
      )}

      {/* Error */}
      {error && (
        <div className="stack" role="alert">
          <p className="error">{error}</p>
          <button className="ghost" onClick={loadReport}>Повторить</button>
        </div>
      )}

      {/* Report */}
      {report && (
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">

          {/* Header: sign chips */}
          <motion.div variants={staggerItem}>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
              {['sun', 'moon', 'rising'].map(k => (
                <span key={k} style={{
                  background: goldBg, border: `1px solid ${goldBorder}`,
                  borderRadius: 20, padding: '4px 12px', fontSize: 13, fontWeight: 600, color: gold
                }}>
                  {CORE_ICONS[k]} {result[k === 'rising' ? 'rising_sign' : `${k}_sign`]}
                </span>
              ))}
            </div>
            {divider}
          </motion.div>

          {/* Overview */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)',
            padding: 'var(--spacing-3)', borderLeft: `3px solid ${gold}`
          }}>
            {sectionTitle('📋', 'Общий портрет')}
            <p style={{ fontSize: 16, lineHeight: 1.75, color: 'rgba(255,255,255,0.88)', margin: 0 }}>
              {report.overview}
            </p>
          </motion.div>

          {/* Core identity: Sun / Moon / Rising accordion */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)'
          }}>
            {sectionTitle('🔮', 'Ядро личности')}
            <div style={{ display: 'flex', gap: 8 }}>
              {['sun', 'moon', 'rising'].map(k => (
                <button
                  key={k}
                  onClick={() => setOpenCore(openCore === k ? null : k)}
                  style={{
                    flex: 1, padding: '10px 6px', borderRadius: 12, cursor: 'pointer',
                    background: openCore === k ? goldBg : 'var(--glass-medium)',
                    border: `1px solid ${openCore === k ? goldBorder : 'transparent'}`,
                    color: openCore === k ? gold : 'var(--text-secondary)',
                    fontSize: 13, fontWeight: 600, transition: 'all 0.2s'
                  }}
                >
                  {CORE_ICONS[k]}<br /><span style={{ fontSize: 11 }}>{CORE_LABELS[k]}</span>
                </button>
              ))}
            </div>
            <AnimatePresence mode="wait">
              {openCore && (
                <motion.p
                  key={openCore}
                  initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{ margin: '12px 0 0', fontSize: 14, lineHeight: 1.65, color: 'rgba(255,255,255,0.82)',
                    borderLeft: `2px solid ${gold}`, paddingLeft: 12, overflow: 'hidden' }}
                >
                  {report[`${openCore}_analysis`]}
                </motion.p>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Life themes accordion */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)'
          }}>
            {sectionTitle('🎯', 'Сферы жизни')}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {['career', 'love', 'finance', 'health', 'growth'].map(key => (
                <div key={key}>
                  <button
                    onClick={() => setOpenTheme(openTheme === key ? null : key)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 12px', borderRadius: 10, cursor: 'pointer', border: 'none',
                      background: openTheme === key ? goldBg : 'transparent',
                      borderLeft: openTheme === key ? `2px solid ${gold}` : '2px solid transparent',
                      transition: 'all 0.2s'
                    }}
                  >
                    <span style={{ fontSize: 14, fontWeight: 600, color: openTheme === key ? gold : 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                      {LIFE_THEME_ICONS[key]} {LIFE_THEME_LABELS[key]}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-tertiary)', transform: openTheme === key ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▼</span>
                  </button>
                  <AnimatePresence>
                    {openTheme === key && (
                      <motion.p
                        initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.22 }}
                        style={{ margin: 0, padding: '6px 12px 10px 24px', fontSize: 14, lineHeight: 1.65,
                          color: 'rgba(255,255,255,0.78)', overflow: 'hidden' }}
                      >
                        {report[key]}
                      </motion.p>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Strengths */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)'
          }}>
            {sectionTitle('✨', 'Сильные стороны')}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {(report.strengths || []).map((s, i) => (
                <span key={i} style={{
                  background: goldBg, border: `1px solid ${goldBorder}`,
                  borderRadius: 20, padding: '5px 13px', fontSize: 13, color: gold, fontWeight: 500
                }}>{s}</span>
              ))}
            </div>
          </motion.div>

          {/* Challenges */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)'
          }}>
            {sectionTitle('⚡', 'Вызовы и точки роста')}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {(report.challenges || []).map((c, i) => (
                <span key={i} style={{
                  background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
                  borderRadius: 20, padding: '5px 13px', fontSize: 13, color: '#FCA5A5', fontWeight: 500
                }}>{c}</span>
              ))}
            </div>
          </motion.div>

          {/* Key aspects */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)'
          }}>
            {sectionTitle('🔭', 'Ключевые аспекты')}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(report.aspects || []).map((a, i) => (
                <div key={i} style={{
                  padding: '10px 12px', borderRadius: 10,
                  background: 'var(--glass-medium)', borderLeft: `2px solid ${goldBorder}`
                }}>
                  <p style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 700, color: gold }}>{a.name}</p>
                  <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'rgba(255,255,255,0.75)' }}>{a.meaning}</p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Recommendations */}
          <motion.div variants={staggerItem} style={{
            background: 'var(--glass-light)', borderRadius: 'var(--radius-xl)', padding: 'var(--spacing-3)'
          }}>
            {sectionTitle('💡', 'Персональные рекомендации')}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(report.tips || []).map((t, i) => (
                <div key={i} style={{
                  padding: '10px 14px', borderRadius: 10,
                  background: goldBg, border: `1px solid ${goldBorder}`
                }}>
                  <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 700, letterSpacing: '0.08em',
                    textTransform: 'uppercase', color: gold }}>{t.area}</p>
                  <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: 'rgba(255,255,255,0.82)' }}>{t.tip}</p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Footer */}
          <motion.div variants={staggerItem}>
            {divider}
            <p style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
              Отчёт сгенерирован AI-астрологом · Gemini Flash · OpenRouter
            </p>
          </motion.div>

        </motion.div>
      )}
    </Shell>
  );
}

function Stories({ onBack, onMissingProfile }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    apiRequest('/v1/forecast/stories')
      .then(async (data) => {
        // Handle ARQ async path: server returns {status:"pending", task_id:"..."}
        if (data?.status === 'pending' && data?.task_id) {
          return pollTask(data.task_id);
        }
        return data;
      })
      .then((data) => {
        setPayload(data);
        setIndex(0);
      })
      .catch((e) => {
        if (isMissingProfileError(e)) {
          onMissingProfile?.();
          return;
        }
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [onMissingProfile]);

  const slides = payload?.slides || [];
  const slide = slides[index];
  const motionPreset = storyCardMotion(slide?.animation);

  useEffect(() => {
    if (slides.length <= 1) return undefined;
    const timer = setTimeout(() => {
      setIndex((prev) => (prev + 1) % slides.length);
    }, STORY_SLIDE_DURATION_MS);
    return () => clearTimeout(timer);
  }, [index, slides.length]);

  const prevSlide = () => {
    if (!slides.length) return;
    setIndex((prev) => (prev - 1 + slides.length) % slides.length);
  };

  const nextSlide = () => {
    if (!slides.length) return;
    setIndex((prev) => (prev + 1) % slides.length);
  };

  return (
    <Shell title="Сторис дня" subtitle="Краткий персональный поток на сегодня" onBack={onBack}>
      {loading && <p className="loading-text">Готовим сторис...</p>}
      {error && <p className="error" role="alert" aria-live="polite">{error}</p>}

      {slide && (
        <motion.div className="stack" variants={staggerContainer} initial="initial" animate="animate">
          <div className="story-progress-row" aria-hidden="true">
            {slides.map((_, progressIndex) => (
              <div className="story-progress-track" key={`story-progress-${progressIndex}`}>
                {progressIndex < index && <span className="story-progress-fill done" />}
                {progressIndex === index && (
                  <span
                    key={`story-progress-active-${index}`}
                    className="story-progress-fill active"
                    style={{ animationDuration: `${STORY_SLIDE_DURATION_MS}ms` }}
                  />
                )}
              </div>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.article
              key={`${payload.date}-${index}-${slide.title}`}
              className={`story-card story-anim-${slide.animation || 'glow'}`}
              initial={motionPreset.initial}
              animate={motionPreset.animate}
              exit={motionPreset.exit}
              transition={motionPreset.transition}
            >
              <small>{payload.date}</small>
              <p className="section-title">{slide.title}</p>
              <p>{slide.body}</p>
              {slide.badge && <div className="chip-row"><span>{slide.badge}</span></div>}

              {(slide.tip || slide.avoid || slide.timing) && (
                <div className="story-insights">
                  {slide.tip && (
                    <div className="story-note story-note-tip">
                      <strong>Практика</strong>
                      <p>{slide.tip}</p>
                    </div>
                  )}
                  {slide.avoid && (
                    <div className="story-note story-note-avoid">
                      <strong>Осторожно</strong>
                      <p>{slide.avoid}</p>
                    </div>
                  )}
                  {slide.timing && (
                    <div className="story-note story-note-timing">
                      <strong>Окно дня</strong>
                      <p>{slide.timing}</p>
                    </div>
                  )}
                </div>
              )}
            </motion.article>
          </AnimatePresence>

          <div className="grid-2">
            <button className="ghost" onClick={prevSlide}>Назад</button>
            <button className="cta" onClick={nextSlide}>Дальше</button>
          </div>

          <small className="story-provider">Источник: {payload?.llm_provider || 'local:fallback'}</small>

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

      {error && <p className="error" role="alert" aria-live="polite">{error}</p>}

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
  const lastTrackedViewRef = useRef('');
  const [deletingProfile, setDeletingProfile] = useState(false);

  const onboardingDone = useMemo(() => localStorage.getItem('onboarding_complete') === '1', []);
  const [hasOnboarding, setHasOnboarding] = useState(onboardingDone);

  const resetToOnboarding = useCallback(() => {
    localStorage.removeItem('onboarding_complete');
    setHasOnboarding(false);
    setView('onboarding');
  }, []);

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

  useEffect(() => {
    const eventName = VIEW_TELEMETRY_EVENTS[view];
    if (!eventName) return;
    if (lastTrackedViewRef.current === view) return;
    lastTrackedViewRef.current = view;

    apiRequest('/v1/telemetry/event', {
      method: 'POST',
      body: JSON.stringify({ event_name: eventName })
    }).catch(() => {
      // ignore telemetry errors
    });
  }, [view]);

  useEffect(() => {
    if (!hasOnboarding) return undefined;
    let active = true;
    apiRequest('/v1/natal/profile/latest')
      .catch((e) => {
        if (!active) return;
        if (isMissingProfileError(e)) {
          resetToOnboarding();
        }
      });

    return () => {
      active = false;
    };
  }, [hasOnboarding, resetToOnboarding]);

  const deleteProfile = useCallback(async () => {
    if (deletingProfile) return;
    const confirmed = window.confirm('Удалить профиль и всю историю? Это действие нельзя отменить.');
    if (!confirmed) return;

    setDeletingProfile(true);
    try {
      await apiRequest('/v1/natal/profile', { method: 'DELETE' });
      resetToOnboarding();
    } catch (e) {
      window.alert(String(e?.message || e || 'Не удалось удалить профиль.'));
    } finally {
      setDeletingProfile(false);
    }
  }, [deletingProfile, resetToOnboarding]);

  if (view === 'onboarding' || !hasOnboarding) {
    return <Onboarding mode="create" onComplete={() => { setHasOnboarding(true); setView('dashboard'); }} />;
  }

  if (view === 'profile_edit') {
    return (
      <Onboarding
        mode="edit"
        onBack={() => setView('dashboard')}
        onComplete={() => {
          setHasOnboarding(true);
          setView('dashboard');
        }}
      />
    );
  }

  if (view === 'natal_mode_select') return (
    <NatalModeSelect
      onBack={() => setView('dashboard')}
      onBasic={() => setView('natal')}
      onPremium={() => setView('natal_premium')}
    />
  );
  if (view === 'natal') return <NatalChart onBack={() => setView('natal_mode_select')} onMissingProfile={resetToOnboarding} />;
  if (view === 'natal_premium') return <NatalPremiumReport onBack={() => setView('natal_mode_select')} onMissingProfile={resetToOnboarding} />;
  if (view === 'stories') return <Stories onBack={() => setView('dashboard')} onMissingProfile={resetToOnboarding} />;
  if (view === 'tarot') return <Tarot onBack={() => setView('dashboard')} />;
  if (view === 'numerology') return <Numerology onBack={() => setView('dashboard')} onMissingProfile={resetToOnboarding} />;

  return (
    <Dashboard
      onOpenNatal={() => setView('natal_mode_select')}
      onOpenStories={() => setView('stories')}
      onOpenTarot={() => setView('tarot')}
      onOpenNumerology={() => setView('numerology')}
      onEditBirthData={() => setView('profile_edit')}
      onDeleteProfile={deleteProfile}
      deletingProfile={deletingProfile}
    />
  );
}
