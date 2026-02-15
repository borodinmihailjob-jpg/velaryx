import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
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

function Shell({ title, subtitle, children, action }) {
  return (
    <motion.main className="screen" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <header className="screen-head">
        <div>
          <h1>{title}</h1>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {action || null}
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
    birth_time: '',
    birth_place: '',
    latitude: '',
    longitude: '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  });

  const submit = async () => {
    setError('');
    setLoading(true);
    try {
      const profile = await apiRequest('/v1/natal/profile', {
        method: 'POST',
        body: JSON.stringify({
          birth_date: form.birth_date,
          birth_time: form.birth_time,
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
    <Shell title="Добро пожаловать" subtitle="Соберем ваш астропрофиль для персональных прогнозов">
      <div className="stack">
        <label>Дата рождения<input type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} /></label>
        <label>Время рождения<input type="time" value={form.birth_time} onChange={(e) => setForm({ ...form, birth_time: e.target.value })} /></label>
        <label>Место рождения<input placeholder="Москва" value={form.birth_place} onChange={(e) => setForm({ ...form, birth_place: e.target.value })} /></label>
        <div className="grid-2">
          <label>Широта<input placeholder="55.7558" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} /></label>
          <label>Долгота<input placeholder="37.6173" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} /></label>
        </div>
        <label>Timezone<input placeholder="Europe/Moscow" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></label>
        <button className="cta" onClick={submit} disabled={loading}>{loading ? 'Считаем карту...' : 'Завершить онбординг'}</button>
        {error ? <p className="error">{error}</p> : null}
      </div>
    </Shell>
  );
}

function Dashboard({ onOpenStories, onOpenTarot, onOpenWishlist, onResetOnboarding }) {
  const [compatLink, setCompatLink] = useState('');
  const [error, setError] = useState('');

  const createCompatLink = async () => {
    setError('');
    try {
      const invite = await apiRequest('/v1/compat/invites', {
        method: 'POST',
        body: JSON.stringify({ ttl_days: 7, max_uses: 1 })
      });
      const url = buildStartAppLink(invite.token);
      setCompatLink(url);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <Shell title="AstroBot" subtitle="Натал, Таро, Совместимость, Wishlist">
      <div className="card-grid">
        <button className="menu-btn" onClick={onOpenStories}>Истории дня</button>
        <button className="menu-btn" onClick={onOpenTarot}>Таро-расклад</button>
        <button className="menu-btn" onClick={createCompatLink}>Совместимость</button>
        <button className="menu-btn" onClick={onOpenWishlist}>Wishlist</button>
      </div>

      {compatLink ? (
        <>
          <p className="link-box">{compatLink}</p>
          <button className="ghost" onClick={() => shareLink(compatLink, 'Проверь нашу совместимость 💫')}>Поделиться ссылкой</button>
        </>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
      <button className="ghost" onClick={onResetOnboarding}>Изменить данные рождения</button>
    </Shell>
  );
}

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
    <Shell title="История дня" subtitle="Персональный ежедневный прогноз" action={<button className="ghost" onClick={onBack}>Назад</button>}>
      {loading ? <p>Загрузка...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {forecast ? (
        <motion.article className="story-card" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
          <small>{forecast.date}</small>
          <h2>Энергия {forecast.energy_score}/100</h2>
          <p>{forecast.summary}</p>
          <div className="chip-row">
            <span>{forecast.payload.sun_sign}</span>
            <span>{forecast.payload.moon_sign}</span>
            <span>{forecast.payload.rising_sign}</span>
          </div>
        </motion.article>
      ) : null}
    </Shell>
  );
}

function Tarot({ onBack }) {
  const [question, setQuestion] = useState('');
  const [reading, setReading] = useState(null);
  const [error, setError] = useState('');

  const draw = async () => {
    setError('');
    try {
      const data = await apiRequest('/v1/tarot/draw', {
        method: 'POST',
        body: JSON.stringify({ spread_type: 'three_card', question })
      });
      setReading(data);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <Shell title="Таро" subtitle="Расклад на 3 карты" action={<button className="ghost" onClick={onBack}>Назад</button>}>
      <label>Вопрос<input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="На чем сфокусироваться сегодня?" /></label>
      <button className="cta" onClick={draw}>Сделать расклад</button>
      {error ? <p className="error">{error}</p> : null}

      {reading ? (
        <div className="item-grid">
          {reading.cards.map((card, idx) => (
            <motion.article key={`${card.card_name}-${idx}`} className="item-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.08 }}>
              <strong>{card.position}. {card.slot_label}</strong>
              <h3>{card.card_name}</h3>
              <span>{card.is_reversed ? 'Перевернутая' : 'Прямая'}</span>
              <p>{card.meaning}</p>
            </motion.article>
          ))}
        </div>
      ) : null}
    </Shell>
  );
}

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
      shareLink(link, 'Твоя очередь проверить совместимость 💫');
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <Shell title="Астрология встречи" subtitle="Откройте совместимость по приглашению">
      <motion.div className="hero" animate={{ rotate: [0, 3, -3, 0] }} transition={{ repeat: Infinity, duration: 4 }}>💫</motion.div>
      <button className="cta" onClick={start} disabled={loading}>{loading ? 'Считаем...' : 'Узнать совместимость'}</button>
      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <motion.section className="story-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <h2>{result.score}% совпадение</h2>
          <p>{result.summary}</p>
          <button className="ghost" onClick={shareOwnLink}>Поделиться своей ссылкой</button>
        </motion.section>
      ) : null}
    </Shell>
  );
}

function WishlistLanding({ token, onBack }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [reserved, setReserved] = useState('');

  useEffect(() => {
    apiRequest(`/v1/public/wishlists/${token}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [token]);

  const reserve = async (itemId) => {
    setError('');
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
    }
  };

  return (
    <Shell title="Wishlist" subtitle="Витрина желаний" action={onBack ? <button className="ghost" onClick={onBack}>Назад</button> : null}>
      {error ? <p className="error">{error}</p> : null}
      {!data ? <p>Загрузка...</p> : null}

      {data ? (
        <>
          <h2>{data.title}</h2>
          <div className="item-grid">
            {data.items.map((item) => (
              <motion.article key={item.id} className="item-card" whileHover={{ y: -3 }}>
                <strong>{item.title}</strong>
                <span>{item.budget_cents ? `${item.budget_cents / 100} ₽` : 'Без бюджета'}</span>
                <span className={item.status === 'reserved' ? 'status status-reserved' : 'status'}>
                  {item.status === 'reserved' ? 'Забронировано' : 'Свободно'}
                </span>
                <button disabled={item.status === 'reserved'} onClick={() => reserve(item.id)}>
                  Забронировать подарок
                </button>
              </motion.article>
            ))}
          </div>
        </>
      ) : null}

      {reserved ? <motion.div className="confetti" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>🎉 Подарок забронирован</motion.div> : null}
    </Shell>
  );
}

function LocalWishlistInfo({ onBack }) {
  return (
    <Shell title="Wishlist" subtitle="Создайте список в API и делитесь wl_ ссылкой" action={<button className="ghost" onClick={onBack}>Назад</button>}>
      <p>Создание карточек wishlist пока через API:</p>
      <code>POST /v1/wishlists</code>
      <code>POST /v1/wishlists/{'{id}'}/items</code>
      <p>Открытие публичной витрины: <code>startapp=wl_...</code></p>
    </Shell>
  );
}

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

  if (view === 'tarot') {
    return <Tarot onBack={() => setView('dashboard')} />;
  }

  if (view === 'wishlist-local') {
    return <LocalWishlistInfo onBack={() => setView('dashboard')} />;
  }

  return (
    <Dashboard
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
