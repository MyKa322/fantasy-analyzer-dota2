import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadPortraitManifest } from "./assets";
import "./index.css";

// Манифест портретов подгружается до первого рендера: без него имена файлов с
// ника не вывести, и вместо лиц были бы инициалы.
loadPortraitManifest().finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
