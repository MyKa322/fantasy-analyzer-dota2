import { useState } from "react";
import {
  GROUP_COLOR,
  GROUP_DIM,
  GROUP_LINE,
  QUALITY_LABEL,
  TRAIT_LABEL,
  emblemIcon,
} from "../assets";
import type { SlotAdvice } from "../api";

function sign(value: number): string {
  if (value > 0) return `+${Math.round(value)}%`;
  if (value < 0) return `−${Math.abs(Math.round(value))}%`;
  return "0%";
}

/**
 * Карточка одного слота баннера — как в игре: иконка, стат, качество, трейт и
 * итоговый процент.
 *
 * Цвет группы живёт на рамке иконки и на линии слева, но никогда не заливает
 * саму иллюстрацию: тонирование убивает рисунок. Цвет при этом не единственный
 * канал — название стата всегда написано текстом.
 */
export default function EmblemCard({ slot }: { slot: SlotAdvice }) {
  const [iconIndex, setIconIndex] = useState(0);
  const icon = emblemIcon(slot.stat);
  const color = GROUP_COLOR[slot.color];

  // Разложение процента: 100 базовых + качество + всё остальное.
  //
  // Остаток намеренно не подписывается трейтом этой эмблемы: он складывается из
  // её собственного трейта и трейтов соседей. Benevolent даёт +20% соседям и
  // ничего себе — приписав остаток самой эмблеме, карточка показывала бы «без
  // трейта +20%» у соседней и «Benevolent 0%» у той, что этот бонус раздаёт.
  const qualityBonus =
    { tier_1: 10, tier_2: 30, tier_3: 60, tier_4: 100, tier_5: 150 }[slot.quality] ?? 0;
  const traitBonus = slot.percent - 100 - qualityBonus;

  return (
    <div
      className="relative flex items-center gap-3 overflow-hidden rounded-md border p-3"
      style={{
        background: "var(--color-bg-card, #16181C)",
        borderColor: GROUP_LINE[slot.color],
      }}
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[2px]"
        style={{ background: color }}
      />

      <div
        className="ml-1 flex h-11 w-11 shrink-0 items-center justify-center rounded"
        style={{ background: GROUP_DIM[slot.color], border: `1px solid ${GROUP_LINE[slot.color]}` }}
      >
        {icon && iconIndex === 0 ? (
          <img
            src={icon}
            alt=""
            className="h-9 w-9 object-contain"
            onError={() => setIconIndex(1)}
          />
        ) : (
          <span className="text-[10px] tracking-wide" style={{ color }}>
            {slot.color.slice(0, 3).toUpperCase()}
          </span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-neutral-100">{slot.label}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-neutral-400">
          <span>
            {QUALITY_LABEL[slot.quality] ?? slot.quality}{" "}
            <span className="tabular">{sign(qualityBonus)}</span>
          </span>
          <span aria-hidden>·</span>
          <span>{slot.trait ? (TRAIT_LABEL[slot.trait] ?? slot.trait) : "без трейта"}</span>
          {Math.round(traitBonus) !== 0 && (
            <>
              <span aria-hidden>·</span>
              <span title="Собственный трейт и трейты соседних эмблем">
                трейты <span className="tabular">{sign(traitBonus)}</span>
              </span>
            </>
          )}
        </div>
      </div>

      <div className="shrink-0 text-right">
        <div className="tabular text-base font-semibold" style={{ color }}>
          {Math.round(slot.percent)}%
        </div>
        <div className="tabular text-xs text-neutral-400">
          {Math.round(slot.points).toLocaleString("ru")}
        </div>
      </div>
    </div>
  );
}
