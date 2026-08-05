import type { TitleAdvice } from "../api";
import { useT } from "../i18n";

/**
 * Coaching Titles: что реально даст титул именно этому игроку или роли.
 *
 * Ожидаемый бонус — процент титула, умноженный на долю карт, где условие
 * выполнялось. Иначе сравнение обманывает: «the Lucky» с его +21% выглядит
 * лучшим из всех, но выпадает примерно на каждой десятой карте, а «the
 * Underdog» с +6% срабатывает в половине.
 */
export default function TitleTable({
  titles,
  limit = 10,
}: {
  titles: TitleAdvice[];
  limit?: number;
}) {
  const { t, tryT } = useT();

  if (!titles.length) return <p className="text-xs text-neutral-500">{t("common.noData")}</p>;

  // Условие и пояснение приходят из снапшота по-русски, но у каждого есть ключ:
  // перевод берётся по ключу, а русский текст остаётся запасным вариантом на
  // случай титула, которого в словаре ещё нет.
  const condition = (title: TitleAdvice) =>
    tryT(`title.${title.key}.condition`, title.condition);
  const note = (title: TitleAdvice) =>
    title.note_key ? tryT(title.note_key, title.note, title.note_params) : title.note;

  const best = titles.find((t) => t.expected_bonus != null);

  return (
    <>
      {best && (
        <p className="mb-2 text-xs text-neutral-400">
          {t("titles.best", {
            title: best.label,
            bonus: Math.round(best.bonus * 100),
            rate: Math.round((best.hit_rate ?? 0) * 100),
            expected: `+${((best.expected_bonus ?? 0) * 100).toFixed(1)}%`,
          })}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-xs">
          <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
            <tr>
              <th className="py-1 text-left">{t("titles.column")}</th>
              <th className="py-1 text-left">{t("titles.condition")}</th>
              <th className="py-1 text-right">{t("titles.gives")}</th>
              <th className="py-1 text-right">{t("titles.fires")}</th>
              <th className="py-1 text-right">{t("titles.expected")}</th>
            </tr>
          </thead>
          <tbody>
            {titles.slice(0, limit).map((title) => (
              <tr key={title.key} className="border-t border-[#20232c]">
                <td className="py-1 text-neutral-200">{title.label}</td>
                <td className="py-1 text-neutral-500" title={note(title)}>
                  {condition(title)}
                </td>
                <td className="tabular py-1 text-right text-neutral-400">
                  +{Math.round(title.bonus * 100)}%
                </td>
                <td className="tabular py-1 text-right text-neutral-400">
                  {title.hit_rate != null ? (
                    `${Math.round(title.hit_rate * 100)}%`
                  ) : (
                    <span className="text-neutral-600">—</span>
                  )}
                </td>
                <td className="tabular py-1 text-right">
                  {title.expected_bonus != null ? (
                    <span className="text-[#c8a24a]">
                      +{(title.expected_bonus * 100).toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-neutral-600" title={note(title)}>
                      {t("titles.unmodelled")}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[11px] text-neutral-500">{t("titles.footnote")}</p>
    </>
  );
}
