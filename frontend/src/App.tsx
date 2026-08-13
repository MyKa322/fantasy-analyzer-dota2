import { useEffect, useState } from "react";
import AdBanner from "./components/AdBanner";
import AdminPanel from "./components/AdminPanel";
import DataPanel from "./components/DataPanel";
import EmblemAnalyzer from "./components/EmblemAnalyzer";
import FantasyPanel from "./components/FantasyPanel";
import GroupPanel from "./components/GroupPanel";
import { ChangelogButton, RepositoryLink } from "./components/HeaderLinks";
import InventoryAnalyzer from "./components/InventoryAnalyzer";
import LanguageSwitch from "./components/LanguageSwitch";
import MatchPanel from "./components/MatchPanel";
import ProfilesPanel from "./components/ProfilesPanel";
import RosterPanel from "./components/RosterPanel";
import StagePanel from "./components/StagePanel";
import TeamsPanel from "./components/TeamsPanel";
import { useT, type MessageKey } from "./i18n";
import { STATIC_MODE, loadSnapshot } from "./snapshot";

// Вкладки, которым нужен живой бэкенд, на опубликованной странице не показываем:
// «Данные» грузят матчи, «Рейтинги» строят историю из базы.
interface Tab {
  key: string;
  label: MessageKey;
  /** У вкладки матча содержимое зависит от адреса, поэтому она рисуется отдельно. */
  element?: React.ReactNode;
  /** Вкладке нужен живой бэкенд. */
  live: boolean;
}

const TABS: Tab[] = ([
  { key: "emblems", label: "app.tab.emblems", element: <EmblemAnalyzer />, live: false },
  { key: "inventory", label: "app.tab.inventory", element: <InventoryAnalyzer />, live: false },
  { key: "profiles", label: "app.tab.profiles", element: <ProfilesPanel />, live: false },
  { key: "match", label: "app.tab.match", live: false },
  { key: "stage", label: "app.tab.stage", live: false },
  { key: "roster", label: "app.tab.roster", element: <RosterPanel />, live: false },
  { key: "predictions", label: "app.tab.predictions", element: <GroupPanel />, live: false },
  { key: "teams", label: "app.tab.teams", element: <TeamsPanel />, live: true },
  { key: "fantasy", label: "app.tab.fantasy", element: <FantasyPanel />, live: true },
  { key: "data", label: "app.tab.data", element: <DataPanel />, live: true },
] satisfies Tab[]).filter((tab) => !STATIC_MODE || !tab.live);

/** Адрес открытого матча: `#/match/8922016200`. */
const MATCH_HASH = /^#\/match\/(\d+)/;

export default function App() {
  const { t, dt } = useT();
  const [active, setActive] = useState("emblems");
  const [matchId, setMatchId] = useState<number | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  // Матч живёт в адресе, а не в состоянии: ссылкой на разбор конкретной карты
  // делятся, и она должна открывать ту же страницу у соседа. Хеш, а не путь, —
  // на GitHub Pages некому переписать `/match/123` в index.html.
  useEffect(() => {
    const read = () => {
      const found = MATCH_HASH.exec(window.location.hash);
      setMatchId(found ? Number(found[1]) : null);
      if (found) setActive("match");
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  const openMatch = (id: number | null) => {
    window.location.hash = id ? `#/match/${id}` : "";
    setMatchId(id);
    setActive("match");
  };

  const openTab = (key: string) => {
    if (key !== "match" && window.location.hash) {
      // Хеш от прошлого матча в адресе соседней вкладки только путает: по такой
      // ссылке страница откроется на матче, а не на том, чем делились.
      history.replaceState(null, "", window.location.pathname + window.location.search);
      setMatchId(null);
    }
    setActive(key);
  };

  // Метку храним как есть, а не отформатированной: её же читает панель
  // обновления, чтобы сравнить открытую вкладку с тем, что лежит на сайте.
  useEffect(() => {
    if (!STATIC_MODE) return;
    loadSnapshot()
      .then((s) => setGeneratedAt(s.generated_at))
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
            {t("app.tagline")}
            {generatedAt && (
              <span className="ml-2 text-neutral-500">
                {t("app.generatedAt", { date: dt(generatedAt) })}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <nav className="flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => openTab(tab.key)}
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
          <ChangelogButton />
          <AdminPanel generatedAt={generatedAt} />
          <RepositoryLink />
        </div>
      </header>

      <AdBanner />

      <main>
        {active === "match" ? (
          <MatchPanel matchId={matchId} onOpen={openMatch} />
        ) : active === "stage" ? (
          // Со страницы групповой стадии открывается разбор конкретной карты,
          // поэтому ей нужен тот же переход, что и таблицам матчей.
          <StagePanel onOpen={openMatch} />
        ) : (
          TABS.find((tab) => tab.key === active)?.element
        )}
      </main>
    </div>
  );
}
