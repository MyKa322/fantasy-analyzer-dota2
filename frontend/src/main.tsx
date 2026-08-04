import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadHeroManifest, loadPortraitManifest } from "./assets";
import "./index.css";

// Манифесты подгружаются до первого рендера: имя файла портрета с ника не
// вывести, а иконку героя — с его id, и без них вместо картинок были бы
// инициалы и голые названия.
Promise.all([loadPortraitManifest(), loadHeroManifest()]).finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
