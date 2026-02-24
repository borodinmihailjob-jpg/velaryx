import { useEffect, useState } from 'react';

import {
  apiRequest,
  askOracle,
  fetchUserHistory,
  fetchWalletSummary,
  persistUserLanguageCode,
  resolveUserLanguageCode,
} from './api';

const QUICK_SIGN_OF_DAY = 'Какой знак дня мне важно увидеть сегодня?';
const ENERGIES = ['Спокойствие', 'Смелость', 'Осторожность'];

function browserTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

function toTimeInputValue(rawValue) {
  if (!rawValue) return '12:00';
  const source = String(rawValue).trim();
  const parts = source.split(':');
  if (parts.length >= 2) {
    const hh = String(parts[0]).padStart(2, '0').slice(0, 2);
    const mm = String(parts[1]).padStart(2, '0').slice(0, 2);
    return `${hh}:${mm}`;
  }
  return '12:00';
}

function defaultBirthForm() {
  return {
    birth_date: '',
    birth_time: '12:00',
    birth_place: '',
    latitude: '',
    longitude: '',
    timezone: browserTimezone(),
  };
}

function parseInterpretation(text) {
  const safeText = String(text || '').trim();
  if (!safeText) {
    return {
      sute: 'Сейчас важнее наблюдать за собой и не спешить с выводами',
      sdelai: 'Сделай один спокойный шаг, который возвращает тебе контроль',
      izbegai: 'Избегай резких решений на эмоциях',
      body: 'Знак ещё формируется. Спроси снова чуть позже или уточни вопрос.',
    };
  }

  const suteMatch = safeText.match(/Суть[:\s]+([^\n.]+)/i);
  const sdelaiMatch = safeText.match(/Сдел[аа]й[:\s]+([^\n.]+)/i);
  const izbegaiMatch = safeText.match(/Избег[аa]й[:\s]+([^\n.]+)/i);

  if (suteMatch && sdelaiMatch && izbegaiMatch) {
    return {
      sute: suteMatch[1].trim(),
      sdelai: sdelaiMatch[1].trim(),
      izbegai: izbegaiMatch[1].trim(),
      body: safeText,
    };
  }

  const sentences = safeText
    .split(/[.!?]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 3);

  return {
    sute: sentences[0] || 'Сохраняй внутреннюю ясность',
    sdelai: sentences[1] || 'Сделай один небольшой шаг по выбранному пути',
    izbegai: sentences[2] || 'Избегай суеты и лишних обещаний',
    body: safeText,
  };
}

function ParchmentCard({ children, className = '', style }) {
  const classNames = ['parchment-card', className].filter(Boolean).join(' ');
  return (
    <div className={classNames} style={style}>
      {children}
    </div>
  );
}

function OracleOrbLoaderMini() {
  return <span className="orb-mini" aria-hidden="true" />;
}

function GoldSealButton({ onClick, loading, disabled, children, type = 'button', title }) {
  return (
    <button
      type={type}
      className="gold-btn"
      onClick={onClick}
      disabled={Boolean(disabled || loading)}
      title={title}
    >
      {loading ? <OracleOrbLoaderMini /> : children}
    </button>
  );
}

function InkButton({ onClick, children, disabled, title, type = 'button', className = '', style }) {
  const classNames = ['ink-btn', className].filter(Boolean).join(' ');
  return (
    <button
      type={type}
      className={classNames}
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={style}
    >
      {children}
    </button>
  );
}

function Chip({ label, onClick }) {
  return (
    <button type="button" className="chip" onClick={onClick}>
      {label}
    </button>
  );
}

function OracleOrbLoader() {
  return (
    <div style={{ position: 'relative', width: 80, height: 80, margin: '32px auto' }} aria-label="loading">
      <div className="water-ring" />
      <div className="water-ring" style={{ animationDelay: '0.8s' }} />
      <div className="water-ring" style={{ animationDelay: '1.6s' }} />
      <div className="orb" />
    </div>
  );
}

function Shell({ title, sub, onBack, children }) {
  return (
    <>
      <div className="shell-header">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="ink-btn"
            style={{ width: 36, minHeight: 36, height: 36, borderRadius: 18, padding: 0 }}
            aria-label="Назад"
          >
            ←
          </button>
        ) : null}
        <div>
          <h2 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>{title}</h2>
          {sub ? <p style={{ fontSize: 12, color: 'var(--smoke-600)', marginTop: 2 }}>{sub}</p> : null}
        </div>
      </div>
      <div className="screen">{children}</div>
    </>
  );
}

function BrandMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <path d="M14 3C9.2 3 6 6.4 6 10.7c0 2.2 1 3.9 2.6 5.1 1.5 1.1 2.2 2 2.2 3.5v1.7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
      <path d="M14 3c4.8 0 8 3.4 8 7.7 0 2.2-1 3.9-2.6 5.1-1.5 1.1-2.2 2-2.2 3.5v1.7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
      <path d="M10 20.8h8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
      <path d="M11.2 24h5.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
      <circle cx="14" cy="10.8" r="1.8" fill="currentColor" opacity="0.75"/>
    </svg>
  );
}

function HomeOracle({ onSubmit, onQuick, initialQuestion, error }) {
  const [q, setQ] = useState(initialQuestion || '');

  useEffect(() => {
    setQ(initialQuestion || '');
  }, [initialQuestion]);

  const CHIPS = ['Любовь', 'Деньги', 'Выбор', 'Путь'];
  const QUICK = [
    'Стоит ли писать первым(ой)?',
    'Где моя удача сейчас?',
    'Что мне важно понять сегодня?',
    'Какой шаг даст результат?',
  ];

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

      {error ? <div className="error-banner">{error}</div> : null}

      <ParchmentCard>
        <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 18, marginBottom: 12 }}>Спроси — и я покажу знак.</h2>
        <textarea
          className="input-field"
          style={{ width: '100%', minHeight: 80, resize: 'none' }}
          placeholder={'Например: "Стоит ли менять работу?"'}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={500}
        />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          {CHIPS.map((c) => (
            <Chip key={c} label={c} onClick={() => setQ(c)} />
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
          {QUICK.map((p) => (
            <Chip key={p} label={p} onClick={() => setQ(p)} />
          ))}
        </div>
      </ParchmentCard>

      <GoldSealButton onClick={() => onSubmit(q)} disabled={!q.trim()}>
        Получить знак
      </GoldSealButton>
      <InkButton onClick={onQuick}>Быстрый знак дня</InkButton>
      <p style={{ fontSize: 12, color: 'var(--smoke-600)', textAlign: 'center' }}>
        Это подсказка, а не приговор. Решение всегда твоё.
      </p>
    </div>
  );
}

function LoadingOracle({ question, setOracleData, setSubview, setError }) {
  useEffect(() => {
    let active = true;

    askOracle(question)
      .then((data) => {
        if (!active) return;
        setOracleData(data);
        setSubview('result');
      })
      .catch((e) => {
        if (!active) return;
        setError(String(e?.message || e || 'Не удалось получить знак'));
        setSubview(null);
      });

    return () => {
      active = false;
    };
  }, [question, setOracleData, setSubview, setError]);

  return (
    <div className="loading-screen">
      <OracleOrbLoader />
      <h2 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Я слушаю воду…</h2>
      <p style={{ color: 'var(--smoke-600)', textAlign: 'center', maxWidth: 280 }}>
        Появится знак — и станет легче дышать.
      </p>
    </div>
  );
}

function ResultOracle({ oracleData, question, onBack, onReset }) {
  const card = oracleData?.cards?.[0] || null;
  const cardName = card?.name || card?.card_name || 'Скрытая карта';
  const number = Number(card?.number ?? card?.position ?? 0);
  const energy = ENERGIES[Math.abs(number) % ENERGIES.length];
  const parsed = parseInterpretation(oracleData?.ai_interpretation);
  const preview = parsed.body.length > 200 ? `${parsed.body.slice(0, 200)}…` : parsed.body;
  const timeLabel = new Date().toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });

  return (
    <Shell title="Знак получен" sub={`Сегодня • ${timeLabel}`} onBack={onBack}>
      {question ? <div className="badge" style={{ alignSelf: 'flex-start' }}>Вопрос: {question}</div> : null}

      <ParchmentCard>
        <span className="badge">Твоя энергия: {energy}</span>
        <h2 style={{ fontFamily: 'Cinzel, serif', marginTop: 12 }}>{cardName}</h2>
        <p style={{ fontSize: 15, lineHeight: 1.6, marginTop: 8, color: 'var(--ink-900)' }}>{preview}</p>
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="bullet-row"><span className="bullet-dot">●</span><span><b>Суть:</b> {parsed.sute}</span></div>
          <div className="bullet-row"><span className="bullet-dot">●</span><span><b>Сделай:</b> {parsed.sdelai}</span></div>
          <div className="bullet-row"><span className="bullet-dot">●</span><span><b>Избегай:</b> {parsed.izbegai}</span></div>
        </div>
      </ParchmentCard>

      <ParchmentCard className="upsell-card">
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Уточнить знак</h3>
        <p style={{ fontSize: 14, color: 'var(--smoke-600)' }}>Я открою скрытый фактор и лучший момент.</p>
        <GoldSealButton onClick={() => window.alert('Скоро')}>Открыть полный ответ • ⭐ Stars</GoldSealButton>
      </ParchmentCard>

      <InkButton onClick={() => window.alert('Скоро')}>Поделиться знаком</InkButton>
      <p style={{ textAlign: 'center', cursor: 'pointer', color: 'var(--azure-500)' }} onClick={onReset}>
        Задать новый вопрос
      </p>
    </Shell>
  );
}

function CompatibilityScreen() {
  const [nameA, setNameA] = useState('');
  const [nameB, setNameB] = useState('');

  return (
    <Shell title="Совместимость" sub="MVP-заглушка до подключения реального API">
      <ParchmentCard>
        <h3 style={{ fontFamily: 'Cinzel, serif', marginBottom: 8 }}>Сравнить энергии</h3>
        <div className="form-grid">
          <label className="field-label">
            Имя / @username 1
            <input className="input-field" value={nameA} onChange={(e) => setNameA(e.target.value)} placeholder="Например: Анна" />
          </label>
          <label className="field-label">
            Имя / @username 2
            <input className="input-field" value={nameB} onChange={(e) => setNameB(e.target.value)} placeholder="Например: Михаил" />
          </label>
        </div>
        <div style={{ marginTop: 12 }}>
          <GoldSealButton disabled title="Скоро">Рассчитать совместимость</GoldSealButton>
        </div>
        <p className="muted-text" style={{ marginTop: 10 }}>
          Функция будет добавлена следующим этапом.
        </p>
      </ParchmentCard>
    </Shell>
  );
}

function WalletEntries({ entries }) {
  if (!entries || entries.length === 0) {
    return <p className="muted-text">Операций пока нет</p>;
  }

  return (
    <div className="stack-sm">
      {entries.slice(0, 5).map((entry, index) => {
        const delta = Number(entry?.delta_stars || 0);
        const sign = delta > 0 ? '+' : '';
        return (
          <div key={String(entry?.id || `${entry?.kind || 'entry'}-${index}`)} className="list-row">
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
  );
}

function HistoryPreview({ reports }) {
  if (!reports || reports.length === 0) {
    return <p className="muted-text">История пока пуста</p>;
  }

  return (
    <div className="stack-sm">
      {reports.slice(0, 5).map((report, index) => (
        <div key={String(report?.id || `${report?.type || 'report'}-${index}`)} className="list-row">
          <div>
            <div className="list-title">{String(report?.type || 'Отчёт')}</div>
            <div className="list-subtitle">
              {report?.created_at ? new Date(report.created_at).toLocaleString('ru-RU') : ''}
            </div>
          </div>
          <div className="list-subtitle">{report?.is_premium ? 'Premium' : 'Basic'}</div>
        </div>
      ))}
    </div>
  );
}

function ProfileScreen({ onEditProfile }) {
  const [wallet, setWallet] = useState({ balance_stars: 0, recent_entries: [] });
  const [walletLoading, setWalletLoading] = useState(true);
  const [walletError, setWalletError] = useState('');
  const [reports, setReports] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const loadWallet = () => {
    setWalletLoading(true);
    setWalletError('');
    fetchWalletSummary()
      .then((data) => {
        setWallet({
          balance_stars: Number(data?.balance_stars || 0),
          recent_entries: Array.isArray(data?.recent_entries) ? data.recent_entries : [],
        });
      })
      .catch((e) => {
        setWallet({ balance_stars: 0, recent_entries: [] });
        setWalletError(String(e?.message || e || 'Не удалось загрузить баланс'));
      })
      .finally(() => setWalletLoading(false));
  };

  useEffect(() => {
    loadWallet();
  }, []);

  useEffect(() => {
    let active = true;
    setHistoryLoading(true);
    fetchUserHistory()
      .then((data) => {
        if (!active) return;
        setReports(Array.isArray(data?.reports) ? data.reports : []);
      })
      .catch(() => {
        if (!active) return;
        setReports([]);
      })
      .finally(() => {
        if (active) setHistoryLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <Shell title="Профиль" sub="Баланс Stars и недавняя история">
      <ParchmentCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <div>
            <div className="muted-text">Баланс сервиса</div>
            <div className="stars-balance">{walletLoading ? '···' : `${Math.max(0, wallet.balance_stars)} ⭐`}</div>
          </div>
          <InkButton onClick={loadWallet} disabled={walletLoading}>Обновить</InkButton>
        </div>
        {walletError ? <div className="error-banner" style={{ marginTop: 10 }}>{walletError}</div> : null}
      </ParchmentCard>

      <ParchmentCard>
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Данные рождения</h3>
        <p className="muted-text">Можно обновить профиль для натальной карты и других расчётов.</p>
        <InkButton onClick={onEditProfile}>Изменить данные</InkButton>
      </ParchmentCard>

      <ParchmentCard>
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Последние операции</h3>
        {walletLoading ? <p className="muted-text">Загрузка...</p> : <WalletEntries entries={wallet.recent_entries} />}
      </ParchmentCard>

      <ParchmentCard>
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>История отчётов</h3>
        {historyLoading ? <p className="muted-text">Загрузка...</p> : <HistoryPreview reports={reports} />}
      </ParchmentCard>
    </Shell>
  );
}

function BottomNav({ tab, setTab }) {
  const tabs = [
    { key: 'oracle', label: 'Оракул' },
    { key: 'compatibility', label: 'Совместимость' },
    { key: 'profile', label: 'Профиль' },
  ];

  return (
    <div className="bottom-nav" role="tablist" aria-label="Навигация">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          className={`nav-tab ${tab === t.key ? 'active' : ''}`}
          onClick={() => setTab(t.key)}
          aria-selected={tab === t.key}
          role="tab"
        >
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}

function Onboarding({ mode = 'create', onComplete, onBack }) {
  const isEditMode = mode === 'edit';
  const [form, setForm] = useState(() => defaultBirthForm());
  const [loading, setLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(isEditMode);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  useEffect(() => {
    if (!isEditMode) return undefined;

    let active = true;
    setLoadingProfile(true);
    setError('');
    setInfo('');

    apiRequest('/v1/natal/profile/latest')
      .then((profile) => {
        if (!active) return;
        setForm({
          birth_date: String(profile?.birth_date || ''),
          birth_time: toTimeInputValue(profile?.birth_time),
          birth_place: String(profile?.birth_place || ''),
          latitude: String(profile?.latitude ?? ''),
          longitude: String(profile?.longitude ?? ''),
          timezone: String(profile?.timezone || browserTimezone()),
        });
        setInfo('Текущие данные загружены. Обновите поля и сохраните.');
      })
      .catch((e) => {
        if (!active) return;
        setInfo(String(e?.message || 'Не удалось загрузить профиль. Заполните форму вручную.'));
      })
      .finally(() => {
        if (active) setLoadingProfile(false);
      });

    return () => {
      active = false;
    };
  }, [isEditMode]);

  const setField = (key, value) => {
    setError('');
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const canSubmit =
    Boolean(form.birth_date) &&
    Boolean(form.birth_time) &&
    Boolean(form.birth_place.trim()) &&
    Number.isFinite(Number(form.latitude)) &&
    Number.isFinite(Number(form.longitude)) &&
    Boolean(form.timezone.trim());

  const submit = async (event) => {
    event.preventDefault();
    if (!canSubmit || loading) return;

    setLoading(true);
    setError('');
    try {
      const profile = await apiRequest('/v1/natal/profile', {
        method: 'POST',
        body: JSON.stringify({
          birth_date: form.birth_date,
          birth_time: form.birth_time || '12:00',
          birth_place: form.birth_place.trim(),
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          timezone: form.timezone.trim() || 'UTC',
        }),
      });

      await apiRequest('/v1/natal/calculate', {
        method: 'POST',
        body: JSON.stringify({ profile_id: profile.id }),
      });

      localStorage.setItem('onboarding_complete', '1');
      onComplete();
    } catch (e) {
      setError(String(e?.message || e || 'Не удалось сохранить профиль'));
    } finally {
      setLoading(false);
    }
  };

  const content = (
    <div className="screen">
      {!isEditMode ? (
        <div className="header-row">
          <div className="brand-mark"><BrandMark /></div>
          <div>
            <h1 style={{ fontFamily: 'Cinzel, serif', fontSize: 24, margin: 0 }}>Velaryx</h1>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--smoke-600)' }}>
              Подготовим профиль для персональных расчётов
            </p>
          </div>
        </div>
      ) : null}

      <ParchmentCard>
        <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 18, marginBottom: 6 }}>
          {isEditMode ? 'Данные рождения' : 'Первичная настройка'}
        </h2>
        <p className="muted-text">
          Укажите дату, время и место рождения. Эти данные нужны для натальной карты и будущих модулей.
        </p>
        {info ? <div className="info-banner">{info}</div> : null}
        {error ? <div className="error-banner">{error}</div> : null}

        <form onSubmit={submit} className="form-grid" style={{ marginTop: 12 }}>
          <label className="field-label">
            Дата рождения
            <input
              type="date"
              className="input-field"
              value={form.birth_date}
              onChange={(e) => setField('birth_date', e.target.value)}
            />
          </label>

          <label className="field-label">
            Время рождения
            <input
              type="time"
              className="input-field"
              value={form.birth_time}
              onChange={(e) => setField('birth_time', e.target.value)}
            />
          </label>

          <label className="field-label">
            Место рождения
            <input
              className="input-field"
              value={form.birth_place}
              onChange={(e) => setField('birth_place', e.target.value)}
              placeholder="Город, страна"
            />
          </label>

          <div className="row-2">
            <label className="field-label">
              Широта
              <input
                className="input-field"
                value={form.latitude}
                onChange={(e) => setField('latitude', e.target.value)}
                placeholder="55.7558"
                inputMode="decimal"
              />
            </label>
            <label className="field-label">
              Долгота
              <input
                className="input-field"
                value={form.longitude}
                onChange={(e) => setField('longitude', e.target.value)}
                placeholder="37.6173"
                inputMode="decimal"
              />
            </label>
          </div>

          <label className="field-label">
            Часовой пояс
            <input
              className="input-field"
              value={form.timezone}
              onChange={(e) => setField('timezone', e.target.value)}
              placeholder="Europe/Moscow"
            />
          </label>

          <div className="row-2" style={{ marginTop: 4 }}>
            {isEditMode ? <InkButton onClick={onBack}>Отмена</InkButton> : <span />}
            <GoldSealButton type="submit" loading={loading} disabled={!canSubmit || loading}>
              {isEditMode ? 'Сохранить' : 'Продолжить'}
            </GoldSealButton>
          </div>
        </form>

        {loadingProfile ? <p className="muted-text" style={{ marginTop: 12 }}>Загрузка профиля...</p> : null}
      </ParchmentCard>
    </div>
  );

  if (isEditMode) {
    return <Shell title="Профиль" sub="Редактирование данных рождения" onBack={onBack}>{content}</Shell>;
  }

  return content;
}

export default function App() {
  const [uiLang, setUiLang] = useState(() => resolveUserLanguageCode());
  const [hasOnboarding, setHasOnboarding] = useState(() => localStorage.getItem('onboarding_complete') === '1');
  const [editingProfile, setEditingProfile] = useState(false);

  const [tab, setTab] = useState('oracle');
  const [subview, setSubview] = useState(null);
  const [question, setQuestion] = useState('');
  const [oracleData, setOracleData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    document.documentElement.lang = uiLang;
  }, [uiLang]);

  useEffect(() => {
    apiRequest('/v1/users/me')
      .then((data) => {
        if (data?.language_code) {
          const normalized = persistUserLanguageCode(data.language_code);
          setUiLang(normalized);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!hasOnboarding) return undefined;

    let active = true;
    apiRequest('/v1/natal/profile/latest')
      .catch((e) => {
        if (!active) return;
        const msg = String(e?.message || e || '').toLowerCase();
        if (e?.status === 404 || msg.includes('not found') || msg.includes('404')) {
          localStorage.removeItem('onboarding_complete');
          setHasOnboarding(false);
        }
      });

    return () => {
      active = false;
    };
  }, [hasOnboarding]);

  const openOracleLoading = (nextQuestion) => {
    const trimmed = String(nextQuestion || '').trim();
    if (!trimmed) return;
    setError(null);
    setQuestion(trimmed);
    setOracleData(null);
    setTab('oracle');
    setSubview('loading');
  };

  const resetOracleHome = () => {
    setSubview(null);
    setOracleData(null);
  };

  if (!hasOnboarding) {
    return <Onboarding mode="create" onComplete={() => setHasOnboarding(true)} />;
  }

  if (editingProfile) {
    return (
      <Onboarding
        mode="edit"
        onBack={() => setEditingProfile(false)}
        onComplete={() => {
          setHasOnboarding(true);
          setEditingProfile(false);
        }}
      />
    );
  }

  let screen = null;
  if (tab === 'oracle') {
    if (subview === 'loading') {
      screen = (
        <LoadingOracle
          question={question}
          setOracleData={setOracleData}
          setSubview={setSubview}
          setError={setError}
        />
      );
    } else if (subview === 'result') {
      screen = (
        <ResultOracle
          oracleData={oracleData}
          question={question}
          onBack={() => setSubview(null)}
          onReset={resetOracleHome}
        />
      );
    } else {
      screen = (
        <HomeOracle
          onSubmit={openOracleLoading}
          onQuick={() => openOracleLoading(QUICK_SIGN_OF_DAY)}
          initialQuestion={question}
          error={error}
        />
      );
    }
  }

  if (tab === 'compatibility') {
    screen = <CompatibilityScreen />;
  }

  if (tab === 'profile') {
    screen = <ProfileScreen onEditProfile={() => setEditingProfile(true)} />;
  }

  const hideBottomNav = tab === 'oracle' && (subview === 'loading' || subview === 'result');

  return (
    <div className="app-shell">
      {screen}
      {!hideBottomNav ? <BottomNav tab={tab} setTab={setTab} /> : null}
    </div>
  );
}
