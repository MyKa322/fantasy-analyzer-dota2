import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Asset note: players/, teams/, and fantasy_craft/ live at the project root,
 * not in public/. They are pulled in via import.meta.glob from src/data/assets.js
 * so Vite fingerprints and serves them without a ~90MB duplication into public/.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
  },
  build: {
    // Portraits are ~1MB each; don't inline anything.
    assetsInlineLimit: 0,
  },
});
