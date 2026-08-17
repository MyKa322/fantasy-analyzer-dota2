// Полоса периодов Fantasy — как две вкладки на экране компендиума.
//
// Она не декоративная: выбор здесь меняет цифры на всех вкладках Fantasy, а
// подпись под названием отвечает на главный вопрос этих дней — сколько ещё
// осталось, чтобы поменять состав.

import { locksIn, useFantasyStage } from "../fantasyStage";
import { useT } from "../i18n";

export default function StageBar() {
  const { t, tryT, tp } = useT();
  const { stages, stage, setStage } = useFantasyStage();

  // Старый снапшот про этапы ничего не знает — тогда и выбирать нечего.
  if (stages.length < 2) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-[11px] tracking-wide text-neutral-500 uppercase">
        {t("stageBar.label")}
      </span>
      {stages.map((entry) => {
        const days = locksIn(entry);
        const active = entry.key === stage;
        return (
          <button
            key={entry.key}
            onClick={() => setStage(entry.key)}
            className={`rounded border px-3 py-1.5 text-left transition ${
              active
                ? "border-[#c8a24a] bg-[#1f1c14]"
                : "border-[#2a2e3a] bg-[#16181e] hover:border-[#4a4433]"
            }`}
          >
            <span
              className={`block text-xs tracking-wide uppercase ${
                active ? "text-[#c8a24a]" : "text-neutral-300"
              }`}
            >
              {tryT(`stageBar.${entry.key}`, entry.label)}
            </span>
            <span className="block text-[10px] text-neutral-500">
              {days === null
                ? t("stageBar.locked")
                : t("stageBar.locksIn", { left: tp("plural.days", days) })}
            </span>
          </button>
        );
      })}
    </div>
  );
}
