import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // На GitHub Pages сайт живёт в подкаталоге /<repo>/, локально — в корне.
  base: process.env.BASE_PATH ?? "/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Бэкенд слушает 8000; проксируем, чтобы не возиться с CORS в разработке.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
