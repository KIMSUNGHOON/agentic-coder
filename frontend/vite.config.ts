import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    },
    watch: {
      // FIXED: Exclude directories to prevent ENOSPC file watcher limit error
      ignored: [
        '**/node_modules/**',
        '**/dist/**',
        '**/dist-ssr/**',
        '**/.git/**',
        '**/backend/**',         // Backend files not needed in frontend watch
        '**/*.log',
        '**/data/**',
        '**/workspace/**',
        '**/__pycache__/**',
        '**/*.pyc'
      ],
      // FIXED: Use polling to avoid ENOSPC errors (slower but more reliable)
      // Set to true if you encounter "System limit for number of file watchers reached"
      usePolling: true,
      interval: 1000,  // Poll every 1 second (balance between responsiveness and CPU usage)
    }
  }
})
