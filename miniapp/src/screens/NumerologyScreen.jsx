import { useState } from 'react';
import { calculateNumerology, fetchNumerologyPremium, pollTask, topUpWalletBalance } from '../api';
import {
  ErrorBanner, GoldButton, InkButton, OrbLoader, ParchmentCard, Shell, TierBadge,
} from '../components/common/index.jsx';

function NumerologyForm({ onFree, onPremium, loading }) {
  const [name, setName] = useState('');
  const [date, setDate] = useState('');

  const canSubmit = name.trim().length > 0;

  return (
    <ParchmentCard>
      <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 17, marginBottom: 10 }}>
        Нумерология судьбы
      </h2>
      <div className="form-grid">
        <label className="field-label">
          Полное имя при рождении
          <input
            className="input-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Анна Ивановна Петрова"
            maxLength={80}
          />
        </label>
        <label className="field-label">
          Дата рождения (опционально)
          <input
            type="date"
            className="input-field"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
      </div>

      <div className="tier-picker" style={{ marginTop: 14 }}>
        <ParchmentCard className="tier-card" style={{ flex: 1 }}>
          <TierBadge premium={false} />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '8px 0 6px', fontSize: 14 }}>Базовый</h3>
          <ul className="tier-features">
            <li>Число жизненного пути</li>
            <li>Число имени</li>
            <li>Краткий разбор</li>
          </ul>
          <GoldButton
            onClick={() => onFree(name.trim(), date)}
            disabled={!canSubmit}
            loading={loading}
            style={{ marginTop: 10, width: '100%' }}
          >
            Рассчитать
          </GoldButton>
        </ParchmentCard>

        <ParchmentCard className="tier-card tier-card--premium" style={{ flex: 1 }}>
          <TierBadge premium />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '8px 0 6px', fontSize: 14 }}>Полный</h3>
          <ul className="tier-features">
            <li>Все из Free +</li>
            <li>10 числовых кодов</li>
            <li>Миссия / Таланты</li>
            <li>Кармические задачи</li>
          </ul>
          <GoldButton
            onClick={() => onPremium(name.trim(), date)}
            disabled={!canSubmit}
            style={{ marginTop: 10, width: '100%' }}
          >
            Открыть ⭐ Stars
          </GoldButton>
        </ParchmentCard>
      </div>
    </ParchmentCard>
  );
}

function NumbersGrid({ numbers }) {
  if (!numbers || Object.keys(numbers).length === 0) return null;

  const LABELS = {
    life_path: 'Путь жизни',
    expression: 'Выражение',
    soul_urge: 'Влечение души',
    personality: 'Личность',
    birthday: 'День рождения',
    personal_year: 'Личный год',
    maturity: 'Число зрелости',
    balance: 'Баланс',
    rational_thought: 'Рац. мышление',
    subconscious_self: 'Подсознание',
  };

  const entries = Object.entries(numbers).filter(([, v]) => v !== null && v !== undefined);

  return (
    <div className="numerology-grid">
      {entries.map(([key, value]) => (
        <div key={key} className="numerology-cell">
          <div className="numerology-cell-value">{value}</div>
          <div className="numerology-cell-label">{LABELS[key] || key}</div>
        </div>
      ))}
    </div>
  );
}

function NumerologyFreeResult({ data }) {
  const numbers = data?.numbers || {};
  const sections = Array.isArray(data?.interpretation_sections) ? data.interpretation_sections : [];

  return (
    <div>
      <ParchmentCard className="natal-signature-card">
        <NumbersGrid numbers={numbers} />
      </ParchmentCard>
      {sections.slice(0, 3).map((sec, i) => (
        <ParchmentCard key={i} style={{ marginTop: 10 }}>
          <div className="section-header">
            <span className="section-icon">{sec.icon || '✦'}</span>
            <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0, fontSize: 15 }}>
              {sec.title || sec.key || `Секция ${i + 1}`}
            </h3>
          </div>
          <p style={{ marginTop: 8, lineHeight: 1.6, fontSize: 14 }}>{sec.text || ''}</p>
        </ParchmentCard>
      ))}
    </div>
  );
}

function NumerologyPremiumResult({ data }) {
  const numbers = data?.numbers || {};
  const report = data?.report || {};

  const REPORT_LABELS = {
    life_purpose: 'Жизненное предназначение',
    talents: 'Таланты и дары',
    karmic_lessons: 'Кармические задачи',
    strengths: 'Сильные стороны',
    challenges: 'Зоны роста',
    relationships: 'Отношения',
    career: 'Карьера',
    spiritual_path: 'Духовный путь',
    current_cycle: 'Текущий цикл',
    advice: 'Совет',
  };

  return (
    <div>
      <ParchmentCard className="natal-signature-card">
        <NumbersGrid numbers={numbers} />
      </ParchmentCard>
      {Object.entries(report).map(([key, value], i) => {
        if (!value || typeof value !== 'string') return null;
        return (
          <ParchmentCard key={i} style={{ marginTop: 10 }}>
            <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>
              {REPORT_LABELS[key] || key}
            </h3>
            <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{value}</p>
          </ParchmentCard>
        );
      })}
    </div>
  );
}

export default function NumerologyScreen({ onBack }) {
  const [phase, setPhase] = useState('form');  // 'form' | 'loading' | 'result'
  const [resultData, setResultData] = useState(null);
  const [isPremium, setIsPremium] = useState(false);
  const [error, setError] = useState('');
  const [lastName, setLastName] = useState('');
  const [lastDate, setLastDate] = useState('');

  const runFree = async (name, date) => {
    setLastName(name);
    setLastDate(date);
    setPhase('loading');
    setError('');
    try {
      const resp = await calculateNumerology(name, date || null);
      if (resp?.task_id) {
        const result = await pollTask(resp.task_id);
        setResultData(result?.result || result);
      } else {
        setResultData(resp);
      }
      setIsPremium(false);
      setPhase('result');
    } catch (e) {
      setError(String(e?.message || 'Числа молчат. Проверь соединение.'));
      setPhase('form');
    }
  };

  const runPremium = async (name, date) => {
    setLastName(name);
    setLastDate(date);
    setPhase('loading');
    setError('');
    try {
      const result = await fetchNumerologyPremium(name, date || null);
      setResultData(result?.result || result);
      setIsPremium(true);
      setPhase('result');
    } catch (e) {
      if (e?.status === 402) {
        const paymentResult = await topUpWalletBalance('numerology_premium').catch(() => null);
        if (paymentResult) {
          await runPremium(name, date);
          return;
        }
      }
      setError(String(e?.message || 'Числа скрыты. Попробуй позже.'));
      setPhase('form');
    }
  };

  return (
    <Shell title="Нумерология" sub="Числовые коды судьбы" onBack={onBack}>
      <ErrorBanner message={error} />

      {phase === 'form' && (
        <NumerologyForm onFree={runFree} onPremium={runPremium} />
      )}

      {phase === 'loading' && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <OrbLoader />
          <p className="muted-text">Числа раскрываются…</p>
        </div>
      )}

      {phase === 'result' && resultData && (
        <>
          {isPremium
            ? <NumerologyPremiumResult data={resultData} />
            : <NumerologyFreeResult data={resultData} />}

          {!isPremium && (
            <ParchmentCard className="upsell-card" style={{ marginTop: 12 }}>
              <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Узнать глубже?</h3>
              <p className="muted-text">10 числовых кодов, кармические задачи и полная карта судьбы</p>
              <GoldButton onClick={() => runPremium(lastName, lastDate)} style={{ marginTop: 10 }}>
                Открыть полный разбор ⭐
              </GoldButton>
            </ParchmentCard>
          )}

          <InkButton onClick={() => setPhase('form')} style={{ marginTop: 8 }}>
            Новый расчёт
          </InkButton>
        </>
      )}
    </Shell>
  );
}
