import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://0.0.0.0:7860', // Replace with your backend URL
        changeOrigin: true,
      }
    }
  }
})
