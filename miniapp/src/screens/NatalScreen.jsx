import { useEffect, useState } from 'react';
import { fetchNatalFree, fetchNatalPremium, pollTask, topUpWalletBalance } from '../api';
import {
  ErrorBanner, GoldButton, InkButton, OrbLoader, ParchmentCard, Shell, TierBadge,
} from '../components/common/index.jsx';

function TierPicker({ onFree, onPremium }) {
  return (
    <div>
      <p className="muted-text" style={{ textAlign: 'center', marginBottom: 16 }}>
        Выбери глубину разбора
      </p>
      <div className="tier-picker">
        <ParchmentCard className="tier-card" style={{ flex: 1 }}>
          <TierBadge premium={false} />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '10px 0 6px' }}>Базовая карта</h3>
          <ul className="tier-features">
            <li>Солнце, Луна, Асцендент</li>
            <li>3 сильные стороны</li>
            <li>2 зоны роста</li>
            <li>Совет дня</li>
          </ul>
          <GoldButton onClick={onFree} style={{ marginTop: 12, width: '100%' }}>
            Получить бесплатно
          </GoldButton>
        </ParchmentCard>

        <ParchmentCard className="tier-card tier-card--premium" style={{ flex: 1 }}>
          <TierBadge premium />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '10px 0 6px' }}>Полный разбор</h3>
          <ul className="tier-features">
            <li>Все из Free +</li>
            <li>Дома и аспекты</li>
            <li>Сценарии отношений/карьеры</li>
            <li>Периоды 30 дней</li>
            <li>1 уточняющий вопрос</li>
          </ul>
          <GoldButton onClick={onPremium} style={{ marginTop: 12, width: '100%' }}>
            Открыть ⭐ Stars
          </GoldButton>
        </ParchmentCard>
      </div>
    </div>
  );
}

function NatalFreeResult({ data }) {
  const sections = data?.interpretation_sections || [];

  return (
    <div>
      <ParchmentCard className="natal-signature-card">
        <div className="natal-triple">
          <div className="natal-triple-item">
            <div className="natal-triple-label">Солнце</div>
            <div className="natal-triple-value">{data?.sun_sign || '—'}</div>
          </div>
          <div className="natal-triple-item">
            <div className="natal-triple-label">Луна</div>
            <div className="natal-triple-value">{data?.moon_sign || '—'}</div>
          </div>
          <div className="natal-triple-item">
            <div className="natal-triple-label">Асцендент</div>
            <div className="natal-triple-value">{data?.rising_sign || '—'}</div>
          </div>
        </div>
      </ParchmentCard>

      {sections.slice(0, 4).map((sec, i) => (
        <ParchmentCard key={i}>
          <div className="section-header">
            <span className="section-icon">{sec.icon || '✦'}</span>
            <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0, fontSize: 15 }}>{sec.title || sec.key || `Секция ${i + 1}`}</h3>
          </div>
          <p style={{ marginTop: 8, lineHeight: 1.6, fontSize: 14 }}>{sec.text || ''}</p>
        </ParchmentCard>
      ))}
    </div>
  );
}

function NatalPremiumResult({ data }) {
  const report = data?.report || {};

  return (
    <div>
      <ParchmentCard className="natal-signature-card">
        <div className="natal-triple">
          <div className="natal-triple-item">
            <div className="natal-triple-label">Солнце</div>
            <div className="natal-triple-value">{data?.sun_sign || '—'}</div>
          </div>
          <div className="natal-triple-item">
            <div className="natal-triple-label">Луна</div>
            <div className="natal-triple-value">{data?.moon_sign || '—'}</div>
          </div>
          <div className="natal-triple-item">
            <div className="natal-triple-label">Асцендент</div>
            <div className="natal-triple-value">{data?.rising_sign || '—'}</div>
          </div>
        </div>
      </ParchmentCard>

      {Object.entries(report).map(([key, value], i) => {
        if (!value || typeof value !== 'string') return null;
        const labels = {
          core_essence: 'Суть натала',
          life_mission: 'Жизненная миссия',
          strengths: 'Сильные стороны',
          challenges: 'Зоны роста',
          relationships: 'Отношения',
          career: 'Карьера',
          next_30_days: 'Ближайшие 30 дней',
        };
        return (
          <ParchmentCard key={i}>
            <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0, fontSize: 15 }}>{labels[key] || key}</h3>
            <p style={{ marginTop: 8, lineHeight: 1.6, fontSize: 14 }}>{value}</p>
          </ParchmentCard>
        );
      })}
    </div>
  );
}

export default function NatalScreen({ onBack }) {
  const [phase, setPhase] = useState('pick');   // 'pick' | 'loading' | 'result'
  const [resultData, setResultData] = useState(null);
  const [isPremium, setIsPremium] = useState(false);
  const [error, setError] = useState('');

  const runFree = async () => {
    setPhase('loading');
    setError('');
    try {
      const resp = await fetchNatalFree();
      if (resp?.task_id) {
        const result = await pollTask(resp.task_id);
        setResultData(result?.result || result);
      } else {
        setResultData(resp);
      }
      setIsPremium(false);
      setPhase('result');
    } catch (e) {
      setError(String(e?.message || 'Вода молчит. Проверь соединение и попробуй снова.'));
      setPhase('pick');
    }
  };

  const runPremium = async () => {
    setPhase('loading');
    setError('');
    try {
      const resp = await fetchNatalPremium();
      if (resp?.task_id) {
        const result = await pollTask(resp.task_id);
        setResultData(result?.result || result);
      } else {
        setResultData(resp);
      }
      setIsPremium(true);
      setPhase('result');
    } catch (e) {
      // 402 — need payment
      if (e?.status === 402) {
        const paymentResult = await topUpWalletBalance('natal_premium').catch(() => null);
        if (paymentResult) {
          await runPremium();
          return;
        }
      }
      setError(String(e?.message || 'Знак скрыт туманом. Попробуй переформулировать запрос.'));
      setPhase('pick');
    }
  };

  return (
    <Shell title="Натальная карта" sub="Карта рождения" onBack={onBack}>
      <ErrorBanner message={error} />

      {phase === 'pick' && (
        <TierPicker onFree={runFree} onPremium={runPremium} />
      )}

      {phase === 'loading' && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <OrbLoader />
          <p className="muted-text">Карта составляется…</p>
        </div>
      )}

      {phase === 'result' && resultData && (
        <>
          {isPremium
            ? <NatalPremiumResult data={resultData} />
            : <NatalFreeResult data={resultData} />}

          {!isPremium && (
            <ParchmentCard className="upsell-card" style={{ marginTop: 12 }}>
              <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Хочешь глубже?</h3>
              <p className="muted-text">Полный разбор домов, аспектов и 30-дневный прогноз</p>
              <GoldButton onClick={runPremium} style={{ marginTop: 10 }}>
                Открыть полную карту ⭐
              </GoldButton>
            </ParchmentCard>
          )}

          <InkButton onClick={() => setPhase('pick')} style={{ marginTop: 8 }}>
            Пересчитать
          </InkButton>
        </>
      )}
    </Shell>
  );
}
