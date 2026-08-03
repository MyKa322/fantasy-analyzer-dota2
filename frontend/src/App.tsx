import { useEffect, useState } from "react";
import DataPanel from "./components/DataPanel";
import EmblemAnalyzer from "./components/EmblemAnalyzer";
import FantasyPanel from "./components/FantasyPanel";
import GroupPanel from "./components/GroupPanel";
import InventoryAnalyzer from "./components/InventoryAnalyzer";
import ProfilesPanel from "./components/ProfilesPanel";
import RosterPanel from "./components/RosterPanel";
import TeamsPanel from "./components/TeamsPanel";
import { STATIC_MODE, formatGeneratedAt, loadSnapshot } from "./snapshot";

// Вкладки, которым нужен живой бэкенд, на опубликованной странице не показываем:
// «Данные» грузят матчи, «Рейтинги» строят историю из базы.
const TABS = [
  { key: "emblems", label: "Эмблемы", element: <EmblemAnalyzer />, live: false },
  { key: "inventory", label: "Мои эмблемы", element: <InventoryAnalyzer />, live: false },
  { key: "profiles", label: "Профили", element: <ProfilesPanel />, live: false },
  { key: "roster", label: "Ростер", element: <RosterPanel />, live: false },
  { key: "predictions", label: "Predictions", element: <GroupPanel />, live: false },
  { key: "teams", label: "Рейтинги", element: <TeamsPanel />, live: true },
  { key: "fantasy", label: "Свой баннер", element: <FantasyPanel />, live: true },
  { key: "data", label: "Данные", element: <DataPanel />, live: true },
].filter((tab) => !STATIC_MODE || !tab.live);

export default function App() {
  const [active, setActive] = useState("emblems");
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!STATIC_MODE) return;
    loadSnapshot()
      .then((s) => setGeneratedAt(formatGeneratedAt(s.generated_at)))
      .catch(() => undefined);
  }, []);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[#2a2e3a] pb-4">
        <div>
          <h1 className="text-xl tracking-[0.18em] text-[#c8a24a] uppercase">
            Compendium Analyzer
          </h1>
          <p className="mt-1 text-xs text-neutral-400">
            The International 2026 — Predictions и Fantasy Draft
            {generatedAt && (
              <span className="ml-2 text-neutral-500">
                · данные от {generatedAt}
              </span>
            )}
          </p>
        </div>
        <nav className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActive(tab.key)}
              className={`rounded px-3 py-1.5 text-xs tracking-wide uppercase transition ${
                active === tab.key
                  ? "bg-[#c8a24a] text-black"
                  : "text-neutral-400 hover:text-neutral-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main>{TABS.find((tab) => tab.key === active)?.element}</main>
    </div>
  );
}
