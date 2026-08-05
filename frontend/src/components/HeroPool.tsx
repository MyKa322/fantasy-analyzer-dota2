import { useState } from "react";
import { heroIcon } from "../assets";
import { useT } from "../i18n";

export interface HeroPoolEntry {
  id: number;
  name: string;
  games: number;
  wins: number;
  players?: { account_id: number; games: number }[];
}

/** Иконка героя. Без манифеста — инициалы, а не битая картинка. */
export function HeroIcon({ id, name, size = 32 }: { id: number; name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const src = heroIcon(id);

  if (!src || failed) {
    return (
      <span
        className="flex shrink-0 items-center justify-center rounded border border-[#2C3138] bg-[#1C1F24] text-[10px] text-neutral-400"
        style={{ width: size, height: size }}
        title={name}
      >
        {name.slice(0, 2)}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt=""
      title={name}
      onError={() => setFailed(true)}
      className="shrink-0 rounded border border-[#2C3138] bg-[#1C1F24] object-cover"
      style={{ width: size, height: size }}
    />
  );
}

/**
 * Пул героев — списком с иконками и долей побед.
 *
 * Полоса под строкой — доля карт от самого частого героя: по ней сразу видно,
 * узкий пул или широкий, а это в драфте значит больше, чем сам список.
 */
export default function HeroPool({
  heroes,
  names,
  limit = 12,
  emptyText,
}: {
  heroes: HeroPoolEntry[];
  /** account_id -> ник: у пары и команды видно, чей это герой. */
  names?: Record<number, string>;
  limit?: number;
  emptyText?: string;
}) {
  const { t, tp } = useT();

  if (!heroes.length) {
    return (
      <p className="text-xs text-neutral-500">{emptyText ?? t("heroPool.empty")}</p>
    );
  }

  const top = heroes.slice(0, limit);
  const most = Math.max(...top.map((h) => h.games));

  return (
    <div className="space-y-1">
      {top.map((hero) => {
        const rate = hero.games ? hero.wins / hero.games : 0;
        const owners = (hero.players ?? [])
          .map((p) => names?.[p.account_id])
          .filter(Boolean)
          .slice(0, 3);
        return (
          <div key={hero.id} className="flex items-center gap-3">
            <HeroIcon id={hero.id} name={hero.name} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span className="truncate text-neutral-100">{hero.name}</span>
                <span className="tabular shrink-0 text-neutral-500">
                  {tp("plural.maps", hero.games)}
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-2">
                <span className="h-1.5 flex-1 overflow-hidden rounded bg-[#20232c]">
                  <span
                    className="block h-full rounded"
                    style={{
                      width: `${Math.round((hero.games / most) * 100)}%`,
                      background:
                        rate >= 0.5 ? "var(--group-green)" : "var(--group-red)",
                    }}
                  />
                </span>
                <span
                  className={`tabular w-9 shrink-0 text-right text-[11px] ${
                    rate >= 0.5 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {Math.round(rate * 100)}%
                </span>
              </div>
              {owners.length > 0 && (
                <div className="truncate text-[10px] text-neutral-600">
                  {owners.join(", ")}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
