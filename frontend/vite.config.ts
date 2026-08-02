import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // На GitHub Pages сайт живёт в подкаталоге /<repo>/, локально — в корне.
  base: process.env.BASE_PATH ?? "/",
  define: {
    // Метка сборки в адресе снапшота. Без неё браузер продолжает отдавать
    // закэшированный JSON: имя файла не меняется, а данные обновляются каждый
    // день — и страница молча показывает вчерашние числа.
    __BUILD_ID__: JSON.stringify(Date.now().toString(36)),
  },
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
