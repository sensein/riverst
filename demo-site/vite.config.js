import { defineConfig } from 'vite';

export default defineConfig({
  base: '/riverst/',
  build: {
    outDir: '../dist-demo',
    emptyOutDir: true,
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_RIVERST_API_URL || 'http://localhost:7860',
        changeOrigin: true,
      },
    },
  },
});
