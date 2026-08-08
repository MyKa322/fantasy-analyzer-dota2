import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadHeroManifest, loadPortraitManifest } from "./assets";
import { I18nProvider, initLocale, localeFromPath } from "./i18n";
import "./index.css";

// Язык берётся из адреса: у каждой языковой версии свой каталог, и до первого
// рендера уже известно, на каком языке писать ошибки загрузки.
const locale = localeFromPath(window.location.pathname, import.meta.env.BASE_URL);

// До первого рендера подгружаются три вещи: словарь языка и манифесты
// портретов с иконками героев. Имя файла портрета с ника не вывести, а иконку
// героя — с его id, и без манифестов вместо картинок были бы инициалы. Словарь
// нужен по той же причине: страница, отрисованная ключами, а потом
// перерисованная подписями, мигает при каждой загрузке.
Promise.all([initLocale(locale), loadPortraitManifest(), loadHeroManifest()]).then(
  ([messages]) => {
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <I18nProvider locale={locale} messages={messages}>
          <App />
        </I18nProvider>
      </StrictMode>,
    );
  },
);
