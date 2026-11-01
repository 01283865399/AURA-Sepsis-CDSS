import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) return 'react-vendor';
          if (id.includes('/recharts/')) return 'charts-vendor';
          if (id.includes('/framer-motion/')) return 'motion-vendor';
          if (id.includes('/react-hook-form/') || id.includes('/zod/') || id.includes('/@hookform/')) return 'forms-vendor';
          if (id.includes('/@tanstack/') || id.includes('/zustand/') || id.includes('/axios/')) return 'data-vendor';
          if (id.includes('/i18next/') || id.includes('/react-i18next/')) return 'i18n-vendor';
          return undefined;
        },
      },
    },
  },
});
