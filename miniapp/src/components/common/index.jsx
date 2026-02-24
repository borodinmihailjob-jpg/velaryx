// Common UI primitives extracted from App.jsx

export function BrandMark() {
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

export function ParchmentCard({ children, className = '', style }) {
  const classNames = ['parchment-card', className].filter(Boolean).join(' ');
  return (
    <div className={classNames} style={style}>
      {children}
    </div>
  );
}

export function OrbLoaderMini() {
  return <span className="orb-mini" aria-hidden="true" />;
}

export function OrbLoader() {
  return (
    <div style={{ position: 'relative', width: 80, height: 80, margin: '32px auto' }} aria-label="loading">
      <div className="water-ring" />
      <div className="water-ring" style={{ animationDelay: '0.8s' }} />
      <div className="water-ring" style={{ animationDelay: '1.6s' }} />
      <div className="orb" />
    </div>
  );
}

export function GoldButton({ onClick, loading, disabled, children, type = 'button', title }) {
  return (
    <button
      type={type}
      className="gold-btn"
      onClick={onClick}
      disabled={Boolean(disabled || loading)}
      title={title}
    >
      {loading ? <OrbLoaderMini /> : children}
    </button>
  );
}

export function InkButton({ onClick, children, disabled, title, type = 'button', className = '', style }) {
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

export function Chip({ label, onClick, active = false }) {
  return (
    <button
      type="button"
      className={['chip', active ? 'chip--active' : ''].filter(Boolean).join(' ')}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

export function Shell({ title, sub, onBack, children, rightSlot }) {
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
        <div style={{ flex: 1 }}>
          <h2 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>{title}</h2>
          {sub ? <p style={{ fontSize: 12, color: 'var(--smoke-600)', marginTop: 2 }}>{sub}</p> : null}
        </div>
        {rightSlot || null}
      </div>
      <div className="screen">{children}</div>
    </>
  );
}

export function BottomNav({ tab, setTab, disabled = false }) {
  const tabs = [
    { key: 'oracle', label: 'Оракул' },
    { key: 'compat', label: 'Совместимость' },
    { key: 'profile', label: 'Профиль' },
  ];

  return (
    <div className="bottom-nav" role="tablist" aria-label="Навигация">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          className={`nav-tab ${tab === t.key ? 'active' : ''}`}
          onClick={() => !disabled && setTab(t.key)}
          aria-selected={tab === t.key}
          role="tab"
          disabled={disabled && tab !== t.key}
        >
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}

export function LoadingScreen({ message = 'Знак формируется…' }) {
  return (
    <div className="loading-screen">
      <OrbLoader />
      <h2 style={{ fontFamily: 'Cinzel, serif', margin: 0 }}>Я слушаю воду…</h2>
      <p style={{ color: 'var(--smoke-600)', textAlign: 'center', maxWidth: 280 }}>{message}</p>
    </div>
  );
}

export function ErrorBanner({ message }) {
  if (!message) return null;
  return <div className="error-banner">{message}</div>;
}

export function TierBadge({ premium }) {
  return (
    <span className={`tier-badge ${premium ? 'tier-badge--premium' : 'tier-badge--free'}`}>
      {premium ? '⭐ Premium' : 'Free'}
    </span>
  );
}
