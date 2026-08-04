import type { TitleAdvice } from "../api";

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
  if (!titles.length) return <p className="text-xs text-neutral-500">Данных нет.</p>;

  const best = titles.find((t) => t.expected_bonus != null);

  return (
    <>
      {best && (
        <p className="mb-2 text-xs text-neutral-400">
          Лучший по ожиданию — <span className="text-[#c8a24a]">{best.label}</span>:{" "}
          {Math.round(best.bonus * 100)}% × {Math.round((best.hit_rate ?? 0) * 100)}% карт ={" "}
          <span className="tabular">+{((best.expected_bonus ?? 0) * 100).toFixed(1)}%</span> к
          очкам.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-xs">
          <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
            <tr>
              <th className="py-1 text-left">Титул</th>
              <th className="py-1 text-left">Условие</th>
              <th className="py-1 text-right">Даёт</th>
              <th className="py-1 text-right">Срабатывает</th>
              <th className="py-1 text-right">Ожидаемо</th>
            </tr>
          </thead>
          <tbody>
            {titles.slice(0, limit).map((title) => (
              <tr key={title.key} className="border-t border-[#20232c]">
                <td className="py-1 text-neutral-200">{title.label}</td>
                <td className="py-1 text-neutral-500" title={title.note}>
                  {title.condition}
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
                    <span className="text-neutral-600" title={title.note}>
                      не оценить
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[11px] text-neutral-500">
        Префиксы считаются по пулу героев: у каждого свой список, и доля карт на этих
        героях — то, как часто титул вообще сработает. Условия, которых нет в данных
        OpenDota, помечены «не оценить» с причиной в подсказке — модель их не выдумывает.
      </p>
    </>
  );
}
