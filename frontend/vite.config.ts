import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    proxy: {
      '/chat': 'http://127.0.0.1:8000',
      '/history': 'http://127.0.0.1:8000'
    }
  }
});
