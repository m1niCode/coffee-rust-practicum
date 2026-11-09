import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  // относительные пути: сборка работает и в корне сайта, и под префиксом (например /kofi/)
  base: './',
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // в режиме разработки запросы /api уходят на Python-сервер (python app.py --no-browser)
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
});
