import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Статика отдаётся FastAPI по пути /app/
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8080' } },
});
