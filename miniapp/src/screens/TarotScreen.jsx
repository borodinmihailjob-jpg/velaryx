import { useState } from 'react';
import { fetchTarotFree } from '../api';
import { ErrorBanner } from '../components/common/index.jsx';

const MUTED = 'rgba(255,255,255,0.55)';
const POSITIONS = ['Прошлое', 'Настоящее', 'Будущее'];

/* ── Primitive components ─────────────────────────────────────────── */

function MWBtn({ onClick, disabled, children, style }) {
  return (
    <button onClick={onClick} disabled={disabled} className="mw-btn-primary" style={style}>
      {children}
    </button>
  );
}

function MWGhost({ onClick, children }) {
  return (
    <button onClick={onClick} className="mw-btn-ghost">
      {children}
    </button>
  );
}

function BackBtn({ onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label="Назад"
      style={{
        background: 'none', border: 'none', color: '#fff',
        fontSize: 22, cursor: 'pointer', padding: '16px 20px',
        lineHeight: 1, display: 'block',
      }}
    >
      ←
    </button>
  );
}

/* Vesica piscis SVG for card back */
function VesicaBack() {
  return (
    <div className="mw-vesica">
      <svg viewBox="0 0 140 220" width="78%" height="78%" fill="none" overflow="visible">
        <defs>
          <filter id="mw-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <ellipse cx="58" cy="110" rx="42" ry="75"
          stroke="rgba(107,142,245,0.85)" strokeWidth="1.5" filter="url(#mw-glow)" />
        <ellipse cx="82" cy="110" rx="42" ry="75"
          stroke="rgba(107,142,245,0.85)" strokeWidth="1.5" filter="url(#mw-glow)" />
      </svg>
    </div>
  );
}

/* ── Phase 1: Deck Selection ──────────────────────────────────────── */

function DeckSelection({ onBack, onNext }) {
  return (
    <div style={{ background: '#000', minHeight: '100dvh', display: 'flex', flexDirection: 'column', color: '#fff' }}>
      <BackBtn onClick={onBack} />
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: '40px 32px 80px', boxSizing: 'border-box',
      }}>
        <h1 style={{
          fontFamily: 'Cinzel, serif', fontSize: 30, fontWeight: 400,
          textAlign: 'center', lineHeight: 1.3, margin: '0 0 16px', letterSpacing: 0.3,
        }}>
          Какую колоду вы используете?
        </h1>
        <p style={{
          color: MUTED, fontSize: 14, textAlign: 'center',
          lineHeight: 1.6, margin: '0 0 48px', maxWidth: 280,
        }}>
          Вы можете получить сопровождение физического чтения или сделать расклад прямо в приложении.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', maxWidth: 320 }}>
          <MWBtn onClick={onNext}>Я использую физическую колоду</MWBtn>
          <MWBtn onClick={onNext}>Я буду гадать в приложении</MWBtn>
        </div>
      </div>
    </div>
  );
}

/* ── Phase 2: Meditation Prep ─────────────────────────────────────── */

function PrepScreen({ onBack, onStart, onSkip }) {
  return (
    <div style={{
      background: '#000', minHeight: '100dvh',
      display: 'flex', flexDirection: 'column', color: '#fff', position: 'relative',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '0', position: 'relative' }}>
        <BackBtn onClick={onBack} />
        <span style={{
          position: 'absolute', left: '50%', transform: 'translateX(-50%)',
          fontFamily: 'Cinzel, serif', fontSize: 15, letterSpacing: 0.3, color: '#fff',
          pointerEvents: 'none',
        }}>
          Постановка вопроса
        </span>
      </div>

      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: '0 32px 40px', boxSizing: 'border-box',
        position: 'relative', overflow: 'hidden',
      }}>
        <div className="mw-orb" style={{ marginBottom: 40 }} />
        <p style={{
          color: 'rgba(255,255,255,0.8)', fontSize: 13, textAlign: 'center',
          lineHeight: 1.75, maxWidth: 300, position: 'relative', zIndex: 1, margin: 0,
        }}>
          Перед чтением карт необходимо очистить свои мысли, в этом вам поможет
          небольшая медитация. Если вы совершаете физическое чтение, сейчас самое
          время перетасовать карты, настроиться.
        </p>
      </div>

      <div style={{ padding: '0 32px 48px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <MWBtn onClick={onStart} style={{ width: '100%' }}>НАЧАТЬ</MWBtn>
        <MWGhost onClick={onSkip}>ПРОПУСТИТЬ</MWGhost>
      </div>
    </div>
  );
}

/* ── Phase 3: Question Input ──────────────────────────────────────── */

function QuestionInput({ onBack, onContinue }) {
  const [q, setQ] = useState('');
  const CHIPS = ['Любовь', 'Деньги', 'Работа', 'Выбор', 'Путь'];

  return (
    <div style={{
      background: '#000', minHeight: '100dvh',
      display: 'flex', flexDirection: 'column', color: '#fff',
    }}>
      <BackBtn onClick={onBack} />
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        padding: '8px 24px 40px', boxSizing: 'border-box',
      }}>
        <h2 style={{
          fontFamily: 'Cinzel, serif', fontSize: 22, fontWeight: 400,
          margin: '0 0 24px', letterSpacing: 0.3,
        }}>
          Задай вопрос картам
        </h2>

        <textarea
          className="mw-input"
          placeholder="Что меня ждёт на этой неделе?"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={300}
          rows={4}
        />

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
          {CHIPS.map((c) => (
            <button
              key={c}
              type="button"
              className={`mw-chip${q === c ? ' mw-chip--active' : ''}`}
              onClick={() => setQ(c)}
            >
              {c}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />
        <MWBtn
          onClick={() => onContinue(q)}
          disabled={!q.trim()}
          style={{ width: '100%', marginTop: 24 }}
        >
          Продолжить
        </MWBtn>
      </div>
    </div>
  );
}

/* ── Loading Screen ───────────────────────────────────────────────── */

function LoadingScreen() {
  return (
    <div style={{
      background: '#000', minHeight: '100dvh',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', color: '#fff',
    }}>
      <div className="mw-orb" />
      <p style={{ color: MUTED, marginTop: 32, fontSize: 14 }}>Карты раскрываются…</p>
    </div>
  );
}

/* ── Phase 5: Card Reveal ─────────────────────────────────────────── */

function CardReveal({ cards, onBack, onFinish }) {
  const [idx, setIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [doneSet, setDoneSet] = useState(new Set());

  const card = cards[idx] || {};
  const cardName = card?.name || card?.card_name || `Карта ${idx + 1}`;
  const isLast = idx === cards.length - 1;

  const handleFlip = () => {
    if (!flipped) {
      setFlipped(true);
      setDoneSet((s) => new Set([...s, idx]));
    }
  };

  const handleNext = () => {
    if (isLast) {
      onFinish();
    } else {
      setIdx((i) => i + 1);
      setFlipped(false);
    }
  };

  return (
    <div className="mw-rays" style={{
      background: '#000', minHeight: '100dvh',
      display: 'flex', flexDirection: 'column', color: '#fff',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', padding: '4px 20px 0',
      }}>
        <button
          onClick={onBack}
          style={{
            background: 'none', border: 'none', color: '#fff',
            fontSize: 22, cursor: 'pointer', padding: '12px 0', lineHeight: 1,
          }}
        >
          ←
        </button>
        <span style={{ fontFamily: 'Cinzel, serif', fontSize: 14, color: MUTED, letterSpacing: 0.5 }}>
          {flipped ? cardName : (POSITIONS[idx] || `Карта ${idx + 1}`)}
        </span>
        <span style={{ width: 22 }} />
      </div>

      {/* Card flip area */}
      <div style={{
        flex: 1, display: 'flex',
        alignItems: 'center', justifyContent: 'center', padding: 20,
      }}>
        <div
          className={`mw-flip-container${flipped ? ' flipped' : ''}`}
          style={{ width: 200, height: 320 }}
          onClick={!flipped ? handleFlip : undefined}
          role={flipped ? undefined : 'button'}
          aria-label={flipped ? undefined : 'Перевернуть карту'}
          tabIndex={flipped ? -1 : 0}
          onKeyDown={(e) => {
            if (!flipped && (e.key === 'Enter' || e.key === ' ')) handleFlip();
          }}
        >
          <div className="mw-flip-inner">
            {/* Card back */}
            <div className="mw-flip-back mw-card">
              <VesicaBack />
            </div>
            {/* Card front */}
            <div className="mw-flip-front mw-card mw-card--front">
              <div style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                height: '100%', padding: '20px 16px', boxSizing: 'border-box',
              }}>
                <div style={{
                  fontFamily: 'Cinzel, serif', fontSize: 10, color: MUTED,
                  letterSpacing: 2, marginBottom: 12, textTransform: 'uppercase',
                }}>
                  {POSITIONS[idx] || `Карта ${idx + 1}`}
                </div>
                <div style={{
                  fontFamily: 'Cinzel, serif', fontSize: 16, fontWeight: 600,
                  textAlign: 'center', lineHeight: 1.4, color: '#fff', marginBottom: 8,
                }}>
                  {cardName}
                </div>
                {card?.meaning && (
                  <div style={{ fontSize: 11, color: MUTED, textAlign: 'center', lineHeight: 1.5 }}>
                    {String(card.meaning).slice(0, 90)}
                    {String(card.meaning).length > 90 ? '…' : ''}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Progress dots */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 24 }}>
        {cards.map((_, i) => (
          <div
            key={i}
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: doneSet.has(i) ? '#fff' : 'rgba(255,255,255,0.25)',
              transition: 'background 0.3s',
            }}
          />
        ))}
      </div>

      {/* Action button */}
      <div style={{ padding: '0 32px 48px' }}>
        {!flipped ? (
          <MWBtn onClick={handleFlip} style={{ width: '100%' }}>перевернуть</MWBtn>
        ) : (
          <MWBtn onClick={handleNext} style={{ width: '100%' }}>
            {isLast ? 'Читать расклад' : 'Следующая карта'}
          </MWBtn>
        )}
      </div>
    </div>
  );
}

/* ── Phase 6: Reading Result ──────────────────────────────────────── */

function ReadingResult({ data, onReset }) {
  const cards = data?.cards || [];
  const interp = String(data?.ai_interpretation || '');

  return (
    <div style={{ background: '#000', minHeight: '100dvh', color: '#fff', overflowY: 'auto' }}>
      <div style={{ padding: '24px 24px 80px', boxSizing: 'border-box' }}>

        {/* Mini cards row */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
          {cards.slice(0, 3).map((card, i) => (
            <div key={i} style={{
              flex: 1, background: '#1c1c1e', borderRadius: 12,
              padding: '12px 8px', textAlign: 'center',
            }}>
              <div style={{
                fontSize: 10, color: MUTED, letterSpacing: 1,
                textTransform: 'uppercase', marginBottom: 6,
              }}>
                {POSITIONS[i] || `Карта ${i + 1}`}
              </div>
              <div style={{ fontFamily: 'Cinzel, serif', fontSize: 11, color: '#fff', lineHeight: 1.3 }}>
                {card?.name || card?.card_name || '—'}
              </div>
            </div>
          ))}
        </div>

        {/* Interpretation */}
        {interp && (
          <p style={{
            fontSize: 14, lineHeight: 1.8,
            color: 'rgba(255,255,255,0.85)',
            margin: '0 0 32px', whiteSpace: 'pre-wrap',
          }}>
            {interp}
          </p>
        )}

        {/* Premium upsell */}
        <div style={{
          padding: 20,
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 16, marginBottom: 16,
        }}>
          <h3 style={{ fontFamily: 'Cinzel, serif', fontSize: 15, margin: '0 0 8px', color: '#fff' }}>
            Узнать глубже?
          </h3>
          <p style={{ fontSize: 13, color: MUTED, margin: '0 0 16px', lineHeight: 1.6 }}>
            Полный расклад со скрытыми факторами и уточняющими вопросами
          </p>
          <MWBtn style={{ width: '100%' }}>Открыть полный расклад ⭐</MWBtn>
        </div>

        <MWGhost onClick={onReset}>Новый расклад</MWGhost>
      </div>
    </div>
  );
}

/* ── Main TarotScreen ─────────────────────────────────────────────── */

export default function TarotScreen({ onBack }) {
  const [phase, setPhase] = useState('deck');
  const [question, setQuestion] = useState('');
  const [resultData, setResultData] = useState(null);
  const [error, setError] = useState('');

  const fetchReading = async (q) => {
    setQuestion(q);
    setPhase('loading');
    setError('');
    try {
      const result = await fetchTarotFree(q);
      setResultData(result);
      setPhase('reveal');
    } catch (e) {
      setError(String(e?.message || 'Карты молчат. Проверь соединение.'));
      setPhase('question');
    }
  };

  const reset = () => {
    setPhase('deck');
    setResultData(null);
    setError('');
    setQuestion('');
  };

  return (
    <>
      {error && <ErrorBanner message={error} />}

      {phase === 'deck' && (
        <DeckSelection onBack={onBack} onNext={() => setPhase('prep')} />
      )}
      {phase === 'prep' && (
        <PrepScreen
          onBack={() => setPhase('deck')}
          onStart={() => setPhase('question')}
          onSkip={() => setPhase('question')}
        />
      )}
      {phase === 'question' && (
        <QuestionInput onBack={() => setPhase('prep')} onContinue={fetchReading} />
      )}
      {phase === 'loading' && <LoadingScreen />}
      {phase === 'reveal' && resultData && (
        <CardReveal
          cards={resultData.cards || []}
          onBack={() => { setPhase('question'); }}
          onFinish={() => setPhase('result')}
        />
      )}
      {phase === 'result' && resultData && (
        <ReadingResult data={resultData} onReset={reset} />
      )}
    </>
  );
}
