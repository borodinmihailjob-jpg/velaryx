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
