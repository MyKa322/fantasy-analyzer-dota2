import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadHeroManifest, loadPortraitManifest } from "./assets";
import { I18nProvider, localeFromPath, setAmbientLocale } from "./i18n";
import "./index.css";

// Язык берётся из адреса: у каждой языковой версии свой каталог, и до первого
// рендера уже известно, на каком языке писать ошибки загрузки.
const locale = localeFromPath(window.location.pathname, import.meta.env.BASE_URL);
setAmbientLocale(locale);

// Манифесты подгружаются до первого рендера: имя файла портрета с ника не
// вывести, а иконку героя — с его id, и без них вместо картинок были бы
// инициалы и голые названия.
Promise.all([loadPortraitManifest(), loadHeroManifest()]).finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <I18nProvider locale={locale}>
        <App />
      </I18nProvider>
    </StrictMode>,
  );
});
