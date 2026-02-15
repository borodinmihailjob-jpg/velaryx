import React from 'react';
import { createRoot } from 'react-dom/client';
import { init } from '@telegram-apps/sdk-react';

import App from './App';
import './styles.css';

try {
  init();
} catch {
  // local browser mode outside Telegram
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
