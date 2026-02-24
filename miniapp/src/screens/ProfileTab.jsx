import { useEffect, useState } from 'react';
import { apiRequest, fetchUserHistory, fetchWalletSummary, topUpWalletBalance } from '../api';
import {
  Chip, GoldButton, InkButton, OrbLoaderMini, ParchmentCard, Shell,
} from '../components/common/index.jsx';

const APP_VERSION = import.meta.env.VITE_APP_VERSION || '1.0.0';

function NatalSignatureCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    apiRequest('/v1/natal/latest')
      .then((d) => { if (active) setData(d); })
      .catch(() => { if (active) setData(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  if (loading) {
    return (
      <ParchmentCard className="natal-signature-card">
        <p className="muted-text" style={{ textAlign: 'center' }}>
          <OrbLoaderMini /> Загружаю натал…
        </p>
      </ParchmentCard>
    );
  }

  if (!data) {
    return (
      <ParchmentCard className="natal-signature-card">
        <p className="muted-text" style={{ textAlign: 'center' }}>
          Натальная карта ещё не рассчитана
        </p>
      </ParchmentCard>
    );
  }

  return (
    <ParchmentCard className="natal-signature-card">
      <div className="natal-triple">
        <div className="natal-triple-item">
          <div className="natal-triple-label">Солнце</div>
          <div className="natal-triple-value">{data.sun_sign || '—'}</div>
        </div>
        <div className="natal-triple-item">
          <div className="natal-triple-label">Луна</div>
          <div className="natal-triple-value">{data.moon_sign || '—'}</div>
        </div>
        <div className="natal-triple-item">
          <div className="natal-triple-label">Асцендент</div>
          <div className="natal-triple-value">{data.rising_sign || '—'}</div>
        </div>
      </div>
    </ParchmentCard>
  );
}

const HISTORY_FILTERS = ['Все', 'Premium', 'Free'];

const TYPE_LABELS = {
  natal_free: 'Натал (базовый)',
  natal_premium: 'Натал (полный)',
  tarot_free: 'Таро (3 карты)',
  tarot_premium: 'Таро (полный)',
  numerology_free: 'Нумерология (базовая)',
  numerology_premium: 'Нумерология (полная)',
  compat_free: 'Совместимость (обзор)',
  compat_premium: 'Совместимость (глубокая)',
  forecast_stories: 'Гороскоп',
  oracle: 'Оракул',
};

function HistoryList({ reports }) {
  const [filter, setFilter] = useState('Все');

  const filtered = reports.filter((r) => {
    if (filter === 'Premium') return r.is_premium;
    if (filter === 'Free') return !r.is_premium;
    return true;
  });

  return (
    <div>
      <div className="history-filter">
        {HISTORY_FILTERS.map((f) => (
          <Chip
            key={f}
            label={f}
            active={filter === f}
            onClick={() => setFilter(f)}
          />
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="muted-text" style={{ textAlign: 'center', padding: '16px 0' }}>
          История пуста
        </p>
      ) : (
        <div className="stack-sm" style={{ marginTop: 8 }}>
          {filtered.slice(0, 20).map((r, i) => (
            <div key={String(r?.id || `${r?.type || 'r'}-${i}`)} className="list-row">
              <div>
                <div className="list-title">
                  {TYPE_LABELS[r?.type] || String(r?.type || 'Отчёт')}
                </div>
                <div className="list-subtitle">
                  {r?.created_at ? new Date(r.created_at).toLocaleString('ru-RU') : ''}
                </div>
              </div>
              <div className="list-subtitle">
                {r?.is_premium ? '⭐' : 'Free'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StarsSection() {
  const [wallet, setWallet] = useState({ balance_stars: 0, recent_entries: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [buying, setBuying] = useState(false);

  const load = () => {
    setLoading(true);
    setError('');
    fetchWalletSummary()
      .then((d) => setWallet({
        balance_stars: Number(d?.balance_stars || 0),
        recent_entries: Array.isArray(d?.recent_entries) ? d.recent_entries : [],
      }))
      .catch((e) => setError(String(e?.message || 'Не удалось загрузить баланс')))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const buyStars = async () => {
    setBuying(true);
    try {
      await topUpWalletBalance('wallet_topup');
      load();
    } catch (e) {
      setError(String(e?.message || 'Не удалось пополнить баланс'));
    } finally {
      setBuying(false);
    }
  };

  return (
    <ParchmentCard>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div>
          <div className="muted-text">Баланс Stars</div>
          <div className="stars-balance">
            {loading ? <OrbLoaderMini /> : `${Math.max(0, wallet.balance_stars)} ⭐`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <InkButton onClick={load} disabled={loading}>↻</InkButton>
          <GoldButton onClick={buyStars} loading={buying} disabled={buying || loading}>
            Купить ⭐
          </GoldButton>
        </div>
      </div>
      {error && <p className="muted-text" style={{ color: 'var(--error)', marginTop: 8 }}>{error}</p>}
      {wallet.recent_entries.length > 0 && (
        <div className="stack-sm" style={{ marginTop: 12 }}>
          {wallet.recent_entries.slice(0, 5).map((entry, i) => {
            const delta = Number(entry?.delta_stars || 0);
            const sign = delta > 0 ? '+' : '';
            return (
              <div key={String(entry?.id || `e-${i}`)} className="list-row">
                <div>
                  <div className="list-title">{String(entry?.kind || 'Операция')}</div>
                  <div className="list-subtitle">
                    {entry?.created_at ? new Date(entry.created_at).toLocaleString('ru-RU') : ''}
                  </div>
                </div>
                <div className="list-value">{`${sign}${delta} ⭐`}</div>
              </div>
            );
          })}
        </div>
      )}
    </ParchmentCard>
  );
}

function AboutSection() {
  return (
    <ParchmentCard className="about-section">
      <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 12px', fontSize: 15 }}>О приложении</h3>

      <div className="about-row">
        <span className="muted-text">Версия</span>
        <span>{APP_VERSION}</span>
      </div>

      <div style={{ marginTop: 14 }}>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--smoke-600)' }}>
          <b>Дисклеймер.</b> Velaryx — развлекательное приложение. Все предсказания, расклады и
          интерпретации носят исключительно информационный характер и не являются советами по
          медицине, финансам, юриспруденции или иным профессиональным сферам.
        </p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--smoke-600)', marginTop: 8 }}>
          Решения принимаете только вы. Ответственность за действия, основанные на материалах
          приложения, лежит исключительно на пользователе.
        </p>
      </div>

      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <button
          type="button"
          className="about-link"
          onClick={() => window.Telegram?.WebApp?.openLink?.('https://t.me/velaryx_bot')}
        >
          Написать в поддержку
        </button>
        <button
          type="button"
          className="about-link"
          onClick={() =>
            window.Telegram?.WebApp?.openLink?.('https://t.me/velaryx_bot?start=privacy')}
        >
          Политика конфиденциальности
        </button>
        <button
          type="button"
          className="about-link"
          onClick={() =>
            window.Telegram?.WebApp?.openLink?.('https://t.me/velaryx_bot?start=terms')}
        >
          Пользовательское соглашение
        </button>
      </div>
    </ParchmentCard>
  );
}

export default function ProfileTab({ onEditProfile }) {
  const [reports, setReports] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchUserHistory()
      .then((d) => { if (active) setReports(Array.isArray(d?.reports) ? d.reports : []); })
      .catch(() => { if (active) setReports([]); })
      .finally(() => { if (active) setHistoryLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <Shell title="Профиль" sub="Ваши данные и история">
      <NatalSignatureCard />

      <ParchmentCard style={{ marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0, fontSize: 15 }}>Данные рождения</h3>
          <InkButton onClick={onEditProfile}>Изменить</InkButton>
        </div>
        <p className="muted-text" style={{ marginTop: 6 }}>
          Дата, время и место рождения для персональных расчётов
        </p>
      </ParchmentCard>

      <div style={{ marginTop: 10 }}>
        <StarsSection />
      </div>

      <ParchmentCard style={{ marginTop: 10 }}>
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 10px', fontSize: 15 }}>
          История отчётов
        </h3>
        {historyLoading ? (
          <p className="muted-text"><OrbLoaderMini /> Загрузка…</p>
        ) : (
          <HistoryList reports={reports} />
        )}
      </ParchmentCard>

      <div style={{ marginTop: 10 }}>
        <AboutSection />
      </div>
    </Shell>
  );
}
