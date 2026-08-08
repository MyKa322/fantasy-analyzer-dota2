// Разрезы выборки: форма, серия, стороны карты, длительность.
//
// Один компонент на обе страницы профиля: у команды и у игрока эти числа
// считаются одинаково и читаются одинаково. Различаются только дополнительные
// строки — под них отведён слот `extra`, чтобы не разводить два почти
// одинаковых блока по двум файлам.

import type { ReactNode } from "react";
import { useT } from "../i18n";
import type { ProfileSplit, ProfileTrends } from "../profiles";

/** Строка разреза: подпись, полоса победности, счёт и процент. */
export function SplitBar({ label, split }: { label: string; split: ProfileSplit }) {
  const { t } = useT();
  const rate = split.games ? split.wins / split.games : 0;

  return (
    <div className="flex items-center gap-2 py-1 text-xs">
      <span className="w-28 shrink-0 truncate text-neutral-500">{label}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded bg-[#20232c]">
        {split.games > 0 && (
          <span
            className="block h-full rounded bg-[#c8a24a]"
            style={{ width: `${Math.round(rate * 100)}%` }}
          />
        )}
      </span>
      <span className="tabular w-14 shrink-0 text-right text-neutral-300">
        {split.games ? `${split.wins}–${split.games - split.wins}` : t("common.dash")}
      </span>
      <span className="tabular w-10 shrink-0 text-right text-neutral-500">
        {split.games ? `${Math.round(rate * 100)}%` : ""}
      </span>
    </div>
  );
}

/** Пара «подпись — значение» для дополнительных строк. */
export function TrendValue({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-[#20232c] py-1 text-xs">
      <span className="text-neutral-500">
        {label}
        {hint && <span className="ml-1 text-neutral-600">{hint}</span>}
      </span>
      <span className="tabular text-neutral-200">{value}</span>
    </div>
  );
}

export default function TrendPanel({
  trends,
  extra,
}: {
  trends: ProfileTrends;
  extra?: ReactNode;
}) {
  const { t, tp, tryT } = useT();

  const rate = (split: ProfileSplit) => (split.games ? split.wins / split.games : null);
  const now = rate(trends.form);
  const before = rate(trends.baseline);
  // Разница в процентных пунктах, а не «во сколько раз»: 40% против 20% — это
  // +20 пунктов, и читается это честнее, чем «рост вдвое» на пяти картах.
  const delta = now !== null && before !== null ? Math.round((now - before) * 100) : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
        <span className="text-neutral-500">{t("trends.form")}</span>
        {trends.form.games ? (
          <span className="tabular text-neutral-100">
            {trends.form.wins}–{trends.form.games - trends.form.wins}
            <span className="ml-1 text-neutral-400">
              ({Math.round((now ?? 0) * 100)}%)
            </span>
          </span>
        ) : (
          <span className="text-neutral-500">{t("trends.formEmpty")}</span>
        )}

        {delta !== null && (
          <span
            className={
              delta > 5 ? "text-emerald-400" : delta < -5 ? "text-red-400" : "text-neutral-400"
            }
            title={t("trends.baselineHint")}
          >
            {delta > 0 ? "↑" : delta < 0 ? "↓" : "="} {Math.abs(delta)} {t("trends.points")}
          </span>
        )}

        {trends.streak !== 0 && (
          <span
            className={`rounded px-2 py-0.5 ${
              trends.streak > 0
                ? "bg-emerald-950 text-emerald-300"
                : "bg-red-950 text-red-300"
            }`}
          >
            {trends.streak > 0
              ? tp("plural.winStreak", trends.streak)
              : tp("plural.lossStreak", -trends.streak)}
          </span>
        )}
      </div>

      <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
            {t("trends.sides")}
          </p>
          {trends.sides.map((split) => (
            <SplitBar
              key={split.key}
              label={split.key === "radiant" ? "Radiant" : "Dire"}
              split={split}
            />
          ))}
        </div>
        <div>
          <p className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
            {t("trends.durations")}
          </p>
          {trends.durations.map((split) => (
            <SplitBar
              key={split.key}
              // Ключ корзины приходит из данных, поэтому подпись ищется словарём
              // с запасным вариантом: новая корзина покажет свой ключ, а не
              // уронит страницу.
              label={tryT(`duration.${split.key}`, split.key)}
              split={split}
            />
          ))}
        </div>
      </div>

      {extra}
    </div>
  );
}
