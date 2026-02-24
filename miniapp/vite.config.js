import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // Telegram iOS WebView can lag behind desktop Telegram in JS syntax support.
    // Transpile modern syntax (optional chaining/nullish coalescing, etc.) to avoid
    // white-screen loading placeholders before WebApp.ready() executes.
    target: 'es2019'
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // allowedHosts: true is intentional — needed for Tailscale Funnel in dev
    allowedHosts: true
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js']
  }
});
