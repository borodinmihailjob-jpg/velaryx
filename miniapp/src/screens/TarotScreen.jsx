import { useState } from 'react';
import { fetchTarotFree, fetchTarotPremium, topUpWalletBalance } from '../api';
import {
  ErrorBanner, GoldButton, InkButton, OrbLoader, ParchmentCard, Shell, TierBadge,
} from '../components/common/index.jsx';

const CARD_EMOJI = ['🂠', '🂡', '🂢', '🂣', '🂤', '🂥', '🂦', '🂧'];

function QuestionForm({ onFree, onPremiumPick, loading }) {
  const [q, setQ] = useState('');
  const CHIPS = ['Любовь', 'Деньги', 'Работа', 'Выбор', 'Путь'];

  return (
    <div>
      <ParchmentCard>
        <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 17, marginBottom: 10 }}>
          Задай вопрос картам
        </h2>
        <textarea
          className="input-field"
          style={{ width: '100%', minHeight: 72, resize: 'none', boxSizing: 'border-box' }}
          placeholder="Что меня ждёт на этой неделе?"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={300}
        />
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
          {CHIPS.map((c) => (
            <button
              key={c}
              type="button"
              className="chip"
              onClick={() => setQ(c)}
            >
              {c}
            </button>
          ))}
        </div>
      </ParchmentCard>

      <div className="tier-picker" style={{ marginTop: 12 }}>
        <ParchmentCard className="tier-card" style={{ flex: 1 }}>
          <TierBadge premium={false} />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '8px 0 6px', fontSize: 15 }}>3 карты</h3>
          <ul className="tier-features">
            <li>Прошлое / Настоящее / Будущее</li>
            <li>Краткое толкование</li>
            <li>Суть — Сделай — Избегай</li>
          </ul>
          <GoldButton
            onClick={() => onFree(q)}
            loading={loading}
            style={{ marginTop: 10, width: '100%' }}
          >
            Получить знак
          </GoldButton>
        </ParchmentCard>

        <ParchmentCard className="tier-card tier-card--premium" style={{ flex: 1 }}>
          <TierBadge premium />
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '8px 0 6px', fontSize: 15 }}>8 карт</h3>
          <ul className="tier-features">
            <li>Все из Free +</li>
            <li>Глубокое чтение</li>
            <li>Скрытые факторы</li>
            <li>Уточняющие вопросы</li>
          </ul>
          <GoldButton
            onClick={() => onPremiumPick(q)}
            style={{ marginTop: 10, width: '100%' }}
          >
            Выбрать карты ⭐
          </GoldButton>
        </ParchmentCard>
      </div>
    </div>
  );
}

function CardPicker({ question, onConfirm, onBack, loading }) {
  const [selected, setSelected] = useState([]);

  const toggle = (idx) => {
    setSelected((prev) =>
      prev.includes(idx)
        ? prev.filter((i) => i !== idx)
        : prev.length < 3
          ? [...prev, idx]
          : prev,
    );
  };

  return (
    <div>
      <ParchmentCard>
        <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 16, marginBottom: 8 }}>
          Выбери 3 карты
        </h2>
        <p className="muted-text" style={{ marginBottom: 12 }}>
          Тапни на карты, которые тебя притягивают. Выбрано: {selected.length} / 3
        </p>
        <div className="tarot-card-grid">
          {Array.from({ length: 8 }, (_, i) => (
            <button
              key={i}
              type="button"
              className={`tarot-card-cell ${selected.includes(i) ? 'tarot-card-cell--selected' : ''}`}
              onClick={() => toggle(i)}
              aria-pressed={selected.includes(i)}
              aria-label={`Карта ${i + 1}`}
            >
              <span className="tarot-card-back" aria-hidden="true">✦</span>
              {selected.includes(i) && (
                <span className="tarot-card-check" aria-hidden="true">✓</span>
              )}
            </button>
          ))}
        </div>
      </ParchmentCard>

      <GoldButton
        onClick={() => onConfirm(question, selected)}
        disabled={selected.length < 3}
        loading={loading}
        style={{ marginTop: 12 }}
      >
        Открыть расклад ⭐
      </GoldButton>
      <InkButton onClick={onBack} style={{ marginTop: 8 }}>Назад</InkButton>
    </div>
  );
}

function TarotFreeResult({ data }) {
  const cards = data?.cards || [];
  const interp = String(data?.ai_interpretation || '');

  const parseBlocks = (text) => {
    const suteMatch = text.match(/Суть[:\s]+([^\n]+)/i);
    const sdelaiMatch = text.match(/Сдел[аа]й[:\s]+([^\n]+)/i);
    const izbegaiMatch = text.match(/Избег[аa]й[:\s]+([^\n]+)/i);
    return {
      sute: suteMatch?.[1]?.trim() || '',
      sdelai: sdelaiMatch?.[1]?.trim() || '',
      izbegai: izbegaiMatch?.[1]?.trim() || '',
      body: text,
    };
  };

  const blocks = parseBlocks(interp);
  const POSITIONS = ['Прошлое', 'Настоящее', 'Будущее'];

  return (
    <div>
      <div className="tarot-result-row">
        {cards.slice(0, 3).map((card, i) => (
          <ParchmentCard key={i} className="tarot-result-card">
            <div className="tarot-result-pos">{POSITIONS[i] || `Карта ${i + 1}`}</div>
            <div className="tarot-result-name">{card?.name || card?.card_name || '—'}</div>
            {card?.meaning && (
              <div className="tarot-result-meaning">{card.meaning}</div>
            )}
          </ParchmentCard>
        ))}
      </div>

      {(blocks.sute || blocks.sdelai || blocks.izbegai) && (
        <ParchmentCard style={{ marginTop: 12 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 10px', fontSize: 15 }}>
            Послание карт
          </h3>
          {blocks.sute && (
            <div className="bullet-row">
              <span className="bullet-dot">●</span>
              <span><b>Суть:</b> {blocks.sute}</span>
            </div>
          )}
          {blocks.sdelai && (
            <div className="bullet-row">
              <span className="bullet-dot">●</span>
              <span><b>Сделай:</b> {blocks.sdelai}</span>
            </div>
          )}
          {blocks.izbegai && (
            <div className="bullet-row">
              <span className="bullet-dot">●</span>
              <span><b>Избегай:</b> {blocks.izbegai}</span>
            </div>
          )}
          {!blocks.sute && !blocks.sdelai && !blocks.izbegai && interp && (
            <p style={{ lineHeight: 1.6, fontSize: 14 }}>{interp}</p>
          )}
        </ParchmentCard>
      )}
    </div>
  );
}

function TarotPremiumResult({ data }) {
  const cards = data?.cards || [];
  const report = data?.report || {};
  const followUps = Array.isArray(data?.follow_up_questions) ? data.follow_up_questions : [];

  const SECTION_LABELS = {
    core_message: 'Ключевое послание',
    hidden_factor: 'Скрытый фактор',
    action_advice: 'Совет к действию',
    timing: 'Тайминг',
    overall: 'Общее прочтение',
  };

  const POSITIONS = ['Прошлое', 'Настоящее', 'Будущее'];

  return (
    <div>
      <div className="tarot-result-row">
        {cards.slice(0, 3).map((card, i) => (
          <ParchmentCard key={i} className="tarot-result-card">
            <div className="tarot-result-pos">{POSITIONS[i] || `Карта ${i + 1}`}</div>
            <div className="tarot-result-name">{card?.name || card?.card_name || '—'}</div>
          </ParchmentCard>
        ))}
      </div>

      {Object.entries(report).map(([key, value], i) => {
        if (!value || typeof value !== 'string') return null;
        return (
          <ParchmentCard key={i} style={{ marginTop: 10 }}>
            <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>
              {SECTION_LABELS[key] || key}
            </h3>
            <p style={{ lineHeight: 1.6, fontSize: 14, margin: 0 }}>{value}</p>
          </ParchmentCard>
        );
      })}

      {followUps.length > 0 && (
        <ParchmentCard style={{ marginTop: 10 }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', margin: '0 0 8px', fontSize: 15 }}>
            Вопросы для размышления
          </h3>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {followUps.map((q, i) => <li key={i} style={{ fontSize: 14 }}>{q}</li>)}
          </ul>
        </ParchmentCard>
      )}
    </div>
  );
}

export default function TarotScreen({ onBack }) {
  const [phase, setPhase] = useState('form');   // 'form' | 'pick' | 'loading' | 'result'
  const [question, setQuestion] = useState('');
  const [resultData, setResultData] = useState(null);
  const [isPremium, setIsPremium] = useState(false);
  const [error, setError] = useState('');

  const runFree = async (q) => {
    setQuestion(q);
    setPhase('loading');
    setError('');
    try {
      const result = await fetchTarotFree(q);
      setResultData(result);
      setIsPremium(false);
      setPhase('result');
    } catch (e) {
      setError(String(e?.message || 'Карты молчат. Проверь соединение.'));
      setPhase('form');
    }
  };

  const openPremiumPick = (q) => {
    setQuestion(q);
    setPhase('pick');
  };

  const runPremium = async (q, _selectedIndices) => {
    setPhase('loading');
    setError('');
    try {
      const result = await fetchTarotPremium('three_card', q);
      setResultData(result);
      setIsPremium(true);
      setPhase('result');
    } catch (e) {
      if (e?.status === 402) {
        const paymentResult = await topUpWalletBalance('tarot_premium').catch(() => null);
        if (paymentResult) {
          await runPremium(q, _selectedIndices);
          return;
        }
      }
      setError(String(e?.message || 'Знак скрыт туманом. Попробуй позже.'));
      setPhase('form');
    }
  };

  const reset = () => {
    setPhase('form');
    setResultData(null);
    setError('');
  };

  return (
    <Shell title="Таро" sub="Расклад карт" onBack={onBack}>
      <ErrorBanner message={error} />

      {phase === 'form' && (
        <QuestionForm
          onFree={runFree}
          onPremiumPick={openPremiumPick}
        />
      )}

      {phase === 'pick' && (
        <CardPicker
          question={question}
          onConfirm={runPremium}
          onBack={() => setPhase('form')}
        />
      )}

      {phase === 'loading' && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <OrbLoader />
          <p className="muted-text">Карты раскрываются…</p>
        </div>
      )}

      {phase === 'result' && resultData && (
        <>
          {isPremium
            ? <TarotPremiumResult data={resultData} />
            : <TarotFreeResult data={resultData} />}

          {!isPremium && (
            <ParchmentCard className="upsell-card" style={{ marginTop: 12 }}>
              <h3 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Узнать глубже?</h3>
              <p className="muted-text">Полный расклад 8 карт со скрытыми факторами и советами</p>
              <GoldButton onClick={() => openPremiumPick(question)} style={{ marginTop: 10 }}>
                Открыть полный расклад ⭐
              </GoldButton>
            </ParchmentCard>
          )}

          <InkButton onClick={reset} style={{ marginTop: 8 }}>
            Новый расклад
          </InkButton>
        </>
      )}
    </Shell>
  );
}
