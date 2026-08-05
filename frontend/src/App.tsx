import { useEffect, useState } from "react";
import DataPanel from "./components/DataPanel";
import EmblemAnalyzer from "./components/EmblemAnalyzer";
import FantasyPanel from "./components/FantasyPanel";
import GroupPanel from "./components/GroupPanel";
import InventoryAnalyzer from "./components/InventoryAnalyzer";
import LanguageSwitch from "./components/LanguageSwitch";
import ProfilesPanel from "./components/ProfilesPanel";
import RosterPanel from "./components/RosterPanel";
import TeamsPanel from "./components/TeamsPanel";
import { useT, type MessageKey } from "./i18n";
import { STATIC_MODE, loadSnapshot } from "./snapshot";

// Вкладки, которым нужен живой бэкенд, на опубликованной странице не показываем:
// «Данные» грузят матчи, «Рейтинги» строят историю из базы.
interface Tab {
  key: string;
  label: MessageKey;
  element: React.ReactNode;
  /** Вкладке нужен живой бэкенд. */
  live: boolean;
}

const TABS: Tab[] = ([
  { key: "emblems", label: "app.tab.emblems", element: <EmblemAnalyzer />, live: false },
  { key: "inventory", label: "app.tab.inventory", element: <InventoryAnalyzer />, live: false },
  { key: "profiles", label: "app.tab.profiles", element: <ProfilesPanel />, live: false },
  { key: "roster", label: "app.tab.roster", element: <RosterPanel />, live: false },
  { key: "predictions", label: "app.tab.predictions", element: <GroupPanel />, live: false },
  { key: "teams", label: "app.tab.teams", element: <TeamsPanel />, live: true },
  { key: "fantasy", label: "app.tab.fantasy", element: <FantasyPanel />, live: true },
  { key: "data", label: "app.tab.data", element: <DataPanel />, live: true },
] satisfies Tab[]).filter((tab) => !STATIC_MODE || !tab.live);

export default function App() {
  const { t, dt } = useT();
  const [active, setActive] = useState("emblems");
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!STATIC_MODE) return;
    loadSnapshot()
      .then((s) => setGeneratedAt(dt(s.generated_at)))
      .catch(() => undefined);
  }, [dt]);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[#2a2e3a] pb-4">
        <div>
          <h1 className="text-xl tracking-[0.18em] text-[#c8a24a] uppercase">
            Compendium Analyzer
          </h1>
          <p className="mt-1 text-xs text-neutral-400">
            {t("app.tagline")}
            {generatedAt && (
              <span className="ml-2 text-neutral-500">
                {t("app.generatedAt", { date: generatedAt })}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
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
                {t(tab.label)}
              </button>
            ))}
          </nav>
          <LanguageSwitch />
        </div>
      </header>

      <main>{TABS.find((tab) => tab.key === active)?.element}</main>
    </div>
  );
}
