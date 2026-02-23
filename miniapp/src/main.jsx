import React from 'react';
import { createRoot } from 'react-dom/client';
import { init } from '@telegram-apps/sdk-react';

import App from './App';
import ErrorBoundary from './ErrorBoundary';
import './styles.css';

try {
  init();
} catch (err) {
  // Running outside Telegram — dev/browser mode
  if (err && err.message) {
    console.warn('[SDK init]', err.message);
  }
}

// Configure Telegram Mini App environment.
// Must happen before React mounts:
//   ready()              — removes Telegram's loading overlay
//   expand()             — opens the app fullscreen (not half-panel)
//   setBackgroundColor   — ensures dark bg for glass-morphism cards
//     (without this, light-theme Telegram users see a white screen
//      because semi-transparent cards become invisible on a white body)
try {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    tg.setBackgroundColor?.('#000000');
    tg.setHeaderColor?.('#000000');
  }
} catch { /* ignore — running outside Telegram */ }

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('[AstroBot] Missing #root element in DOM');
}

createRoot(rootElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
