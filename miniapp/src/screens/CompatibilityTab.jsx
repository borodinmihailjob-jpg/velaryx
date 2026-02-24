import { useState } from 'react';
import { fetchCompatFree, fetchCompatPremium, topUpWalletBalance } from '../api';
import {
  ErrorBanner, GoldButton, InkButton, OrbLoader, ParchmentCard, Shell, TierBadge,
} from '../components/common/index.jsx';

const COMPAT_TYPES = [
  { key: 'romantic', label: 'Пара', icon: '♥' },
  { key: 'friendship', label: 'Дружба', icon: '✦' },
  { key: 'work', label: 'Работа', icon: '◆' },
];

function CompatTypeSelector({ value, onChange }) {
  return (
    <div className="compat-type-selector">
      {COMPAT_TYPES.map((t) => (
        <button
          key={t.key}
          type="button"
          className={`compat-type-btn ${value === t.key ? 'compat-type-btn--active' : ''}`}
          onClick={() => onChange(t.key)}
        >
          <span className="compat-type-icon">{t.icon}</span>
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}

function CompatDataForm({ compatType, onNext, onBack }) {
  const [date1, setDate1] = useState('');
  const [date2, setDate2] = useState('');
  const [name1, setName1] = useState('');
  const [name2, setName2] = useState('');
  const [validationError, setValidationError] = useState('');

  const today = new Date().toISOString().split('T')[0];

  const validate = () => {
    if (!date1 || !date2) return 'Укажи даты рождения обоих';
    if (date1 > today || date2 > today) return 'Дата рождения не может быть в будущем';
    if (name1.length > 32 || name2.length > 32) return 'Имя не может быть длиннее 32 символов';
    return '';
  };

  const handleNext = () => {
    const err = validate();
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError('');
    onNext({
      compat_type: compatType,
      birth_date_1: date1,
      birth_date_2: date2,
      name_1: name1.trim() || null,
      name_2: name2.trim() || null,
    });
  };

  const typeLabel = COMPAT_TYPES.find((t) => t.key === compatType)?.label || '';

  return (
    <div>
      <ParchmentCard>
        <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 16, marginBottom: 12 }}>
          {typeLabel}: данные для расчёта
        </h2>
        {validationError && <ErrorBanner message={validationError} />}
        <div className="form-grid">
          <div>
            <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 8px', fontFamily: 'Cinzel, serif' }}>
              Первый человек
            </p>
            <label className="field-label">
              Имя (опционально)
              <input
                className="input-field"
                value={name1}
                onChange={(e) => setName1(e.target.value)}
                placeholder="Анна"
                maxLength={32}
              />
            </label>
            <label className="field-label" style={{ marginTop: 8 }}>
              Дата рождения
              <input
                type="date"
                className="input-field"
                value={date1}
                onChange={(e) => setDate1(e.target.value)}
                max={today}
              />
            </label>
          </div>

          <div style={{ marginTop: 12 }}>
            <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 8px', fontFamily: 'Cinzel, serif' }}>
              Второй человек
            </p>
            <label className="field-label">
              Имя (опционально)
              <input
                className="input-field"
                value={name2}
                onChange={(e) => setName2(e.target.value)}
                placeholder="Михаил"
                maxLength={32}
              />
            </label>
            <label className="field-label" style={{ marginTop: 8 }}>
              Дата рождения
              <input
                type="date"
                className="input-field"
                value={date2}
                onChange={(e) => setDate2(e.target.value)}
                max={today}
              />
            </label>
          </div>
        </div>
      </ParchmentCard>

      <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
        <InkButton onClick={onBack} style={{ flex: 1 }}>Назад</InkButton>
        <GoldButton
          onClick={handleNext}
          disabled={!date1 || !date2}
          style={{ flex: 2 }}
        >
          Далее
        </GoldButton>
      </div>
    </div>
  );
}

function CompatTierPicker({ formData, onFree, onPremium }) {
  return (
    <div>
      <p className="muted-text" style={{ textAlign: 'center', marginBottom: 16 }}>
        Выбери глубину анализа
      </p>
      <div className="tier-picker">
        <ParchmentCard className="tier-card" style={{ flex: 1 }}>
          <TierBadge premium={false} />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '10px 0 6px', fontSize: 15 }}>Обзор</h3>
          <ul className="tier-features">
            <li>Процент совместимости</li>
            <li>Краткая суть</li>
            <li>Сильные стороны</li>
            <li>Риски</li>
          </ul>
          <GoldButton onClick={() => onFree(formData)} style={{ marginTop: 12, width: '100%' }}>
            Бесплатно
          </GoldButton>
        </ParchmentCard>

        <ParchmentCard className="tier-card tier-card--premium" style={{ flex: 1 }}>
          <TierBadge premium />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '10px 0 6px', fontSize: 15 }}>Глубокий</h3>
          <ul className="tier-features">
            <li>Все из Free +</li>
            <li>Зелёные флаги</li>
            <li>Красные флаги</li>
            <li>Советы и тайминг</li>
          </ul>
          <GoldButton onClick={() => onPremium(formData)} style={{ marginTop: 12, width: '100%' }}>
            Открыть ⭐ Stars
          </GoldButton>
        </ParchmentCard>
      </div>
    </div>
  );
}

function CompatMedallion({ score }) {
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  let color = 'var(--azure-500)';
  if (pct >= 75) color = '#4caf50';
  else if (pct >= 50) color = '#ff9800';
  else color = '#f44336';

  return (
    <div className="compat-medallion" style={{ '--score-color': color }}>
      <div className="compat-medallion-ring">
        <div className="compat-medallion-value">{pct}</div>
        <div className="compat-medallion-pct">%</div>
      </div>
      <div className="compat-medallion-label">совместимость</div>
    </div>
  );
}

function CompatFreeResult({ data, formData, onPremium }) {
  const result = data?.result || data || {};
  const p1 = formData?.name_1 || 'Человек 1';
  const p2 = formData?.name_2 || 'Человек 2';

  return (
    <div>
      <ParchmentCard className="natal-signature-card" style={{ textAlign: 'center' }}>
        <p className="muted-text" style={{ marginBottom: 8 }}>{p1} & {p2}</p>
        <CompatMedallion score={result.compatibility_score} />
      </ParchmentCard>

      {result.summary && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Суть</h3>
          <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{result.summary}</p>
        </ParchmentCard>
      )}
      {result.strength && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Сильные стороны</h3>
          <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{result.strength}</p>
        </ParchmentCard>
      )}
      {result.risk && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Риски</h3>
          <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{result.risk}</p>
        </ParchmentCard>
      )}
      {result.advice && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Совет</h3>
          <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{result.advice}</p>
        </ParchmentCard>
      )}

      <ParchmentCard className="upsell-card" style={{ marginTop: 12 }}>
        <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Узнать глубже?</h3>
        <p className="muted-text">Зелёные и красные флаги, советы по коммуникации и окна гармонии</p>
        <GoldButton onClick={() => onPremium(formData)} style={{ marginTop: 10 }}>
          Глубокий разбор ⭐
        </GoldButton>
      </ParchmentCard>
    </div>
  );
}

function CompatPremiumResult({ data, formData }) {
  const p1 = formData?.name_1 || 'Человек 1';
  const p2 = formData?.name_2 || 'Человек 2';

  const greenFlags = Array.isArray(data?.green_flags) ? data.green_flags : [];
  const redFlags = Array.isArray(data?.red_flags) ? data.red_flags : [];
  const tips = Array.isArray(data?.communication_tips) ? data.communication_tips : [];
  const windows = Array.isArray(data?.time_windows) ? data.time_windows : [];
  const followUps = Array.isArray(data?.follow_up_questions) ? data.follow_up_questions : [];

  return (
    <div>
      <ParchmentCard className="natal-signature-card" style={{ textAlign: 'center' }}>
        <p className="muted-text" style={{ marginBottom: 8 }}>{p1} & {p2}</p>
        <CompatMedallion score={data?.compatibility_score} />
      </ParchmentCard>

      {data?.summary && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Суть</h3>
          <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{data.summary}</p>
        </ParchmentCard>
      )}

      {greenFlags.length > 0 && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15, color: '#4caf50' }}>
            Зелёные флаги
          </h3>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {greenFlags.map((f, i) => <li key={i} style={{ fontSize: 14 }}>{f}</li>)}
          </ul>
        </ParchmentCard>
      )}

      {redFlags.length > 0 && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15, color: '#f44336' }}>
            Красные флаги
          </h3>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {redFlags.map((f, i) => <li key={i} style={{ fontSize: 14 }}>{f}</li>)}
          </ul>
        </ParchmentCard>
      )}

      {tips.length > 0 && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Коммуникация</h3>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {tips.map((t, i) => <li key={i} style={{ fontSize: 14 }}>{t}</li>)}
          </ul>
        </ParchmentCard>
      )}

      {windows.length > 0 && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Окна гармонии</h3>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {windows.map((w, i) => <li key={i} style={{ fontSize: 14 }}>{w}</li>)}
          </ul>
        </ParchmentCard>
      )}

      {followUps.length > 0 && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>Для размышления</h3>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {followUps.map((q, i) => <li key={i} style={{ fontSize: 14 }}>{q}</li>)}
          </ul>
        </ParchmentCard>
      )}
    </div>
  );
}

export default function CompatibilityTab() {
  // step: 'type' | 'form' | 'tier' | 'loading' | 'result'
  const [step, setStep] = useState('type');
  const [compatType, setCompatType] = useState('romantic');
  const [formData, setFormData] = useState(null);
  const [resultData, setResultData] = useState(null);
  const [isPremium, setIsPremium] = useState(false);
  const [error, setError] = useState('');

  const runFree = async (data) => {
    setFormData(data);
    setStep('loading');
    setError('');
    try {
      const result = await fetchCompatFree(data);
      setResultData(result);
      setIsPremium(false);
      setStep('result');
    } catch (e) {
      setError(String(e?.message || 'Расчёт не удался. Проверь соединение.'));
      setStep('tier');
    }
  };

  const runPremium = async (data) => {
    setFormData(data);
    setStep('loading');
    setError('');
    try {
      const result = await fetchCompatPremium(data);
      setResultData(result);
      setIsPremium(true);
      setStep('result');
    } catch (e) {
      if (e?.status === 402) {
        const paymentResult = await topUpWalletBalance('compat_premium').catch(() => null);
        if (paymentResult) {
          await runPremium(data);
          return;
        }
      }
      setError(String(e?.message || 'Расчёт не удался. Попробуй позже.'));
      setStep('tier');
    }
  };

  const reset = () => {
    setStep('type');
    setResultData(null);
    setError('');
  };

  return (
    <Shell title="Совместимость" sub="Анализ энергий двух людей">
      <ErrorBanner message={error} />

      {step === 'type' && (
        <div>
          <p className="muted-text" style={{ textAlign: 'center', marginBottom: 16 }}>
            Выбери тип отношений
          </p>
          <CompatTypeSelector value={compatType} onChange={setCompatType} />
          <GoldButton onClick={() => setStep('form')} style={{ marginTop: 20 }}>
            Продолжить
          </GoldButton>
        </div>
      )}

      {step === 'form' && (
        <CompatDataForm
          compatType={compatType}
          onNext={(data) => {
            setFormData(data);
            setStep('tier');
          }}
          onBack={() => setStep('type')}
        />
      )}

      {step === 'tier' && (
        <>
          <CompatTierPicker
            formData={formData}
            onFree={runFree}
            onPremium={runPremium}
          />
          <InkButton onClick={() => setStep('form')} style={{ marginTop: 12 }}>
            Изменить данные
          </InkButton>
        </>
      )}

      {step === 'loading' && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <OrbLoader />
          <p className="muted-text">Считаю совместимость…</p>
        </div>
      )}

      {step === 'result' && resultData && (
        <>
          {isPremium
            ? <CompatPremiumResult data={resultData} formData={formData} />
            : <CompatFreeResult data={resultData} formData={formData} onPremium={runPremium} />}

          <InkButton onClick={reset} style={{ marginTop: 12 }}>
            Новый расчёт
          </InkButton>
        </>
      )}
    </Shell>
  );
}
