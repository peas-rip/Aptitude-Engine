import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Dev proxy — the backend ships NO CORS middleware (API_INTEGRATION.md §1.5),
 * so the browser must only ever talk to our own origin.
 *
 *   browser  /api/qme/<path>   →   http://localhost:8000/api/v1/<path>
 *
 * The client's default baseUrl is `/api/qme` (qme-client.ts), which keeps the
 * real API version and the optional API key out of the bundle.
 *
 * `loadEnv` is used rather than `process.env` so this file needs no @types/node.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', ['VITE_', 'QME_']);

  const apiOrigin = env.QME_BASE_URL || 'http://localhost:8000';
  // Only attach a key when one is configured; the browser never sees it.
  // QME_API_KEY unset (dev) => the API is open (API_INTEGRATION.md §1.3).
  const apiKey = env.QME_API_KEY;

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api/qme': {
          target: apiOrigin,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api\/qme/, '/api/v1'),
          configure: (proxy) => {
            if (!apiKey) return;
            proxy.on('proxyReq', (proxyReq) => proxyReq.setHeader('X-API-Key', apiKey));
          },
        },
      },
    },
  };
});
