import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

function normalizeBase(value: string | undefined): string {
  if (!value || value === '/') return '/';
  return `/${value.replace(/^\/+|\/+$/g, '')}/`;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    // Asset namespace is deliberately independent from React route paths.
    // The SPA still owns /buyer, /seller and /admin.
    base: normalizeBase(env.VITE_ASSET_BASE_URL || '/b2b-static/'),
    plugins: [react()],
    server: {
      port: 5176,
      strictPort: true,
      allowedHosts: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
    },
  };
});
