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
      '/history': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/dashboard': 'http://127.0.0.1:8000',
      '/inventory': 'http://127.0.0.1:8000',
      '/purchase-orders': 'http://127.0.0.1:8000',
      '/leaves': 'http://127.0.0.1:8000',
      '/vendors': 'http://127.0.0.1:8000'
    }
  }
});
