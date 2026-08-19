// Сетка плей-офф: восемь команд, double elimination, четырнадцать серий.
//
// Рисуется деревом, а не колонками, и это не украшение. Вопрос к сетке всегда
// один: «куда отсюда попадает победитель» — на него отвечает линия, а колонка
// рядом заставляет искать ответ глазами. Поэтому раскладка повторяет ту, что
// показывает компендиум: верхняя лента, под ней нижняя, гранд-финал справа.
//
// Места считаются по дереву: четвертьфиналы стоят с равным шагом, каждая
// следующая серия — посередине между теми, кто её кормит. Так координаты
// выводятся из структуры, а не проставляются руками, и при любой правке сетки
// линии остаются на местах.
//
// В пустое место вписан прогноз, и он берётся из одного связного хода турнира:
// сетка пройдена целиком, в каждой серии дальше идёт фаворит, проигравший
// уходит туда, куда ведёт структура. Отдельно взятая «самая вероятная команда
// каждого места» складывалась бы в сетку, которой не бывает — одна и та же
// команда стояла бы и в финале верхней, и в полуфинале нижней, куда после
// выигранного полуфинала верхней попасть уже нельзя.
//
// Два числа не смешиваются: у участника показан шанс выиграть серию, у прогноза
// — шанс прийти на это место именно этой веткой, и подписаны они по-разному.

import { useEffect, useMemo, useState } from "react";
import { teamCrest } from "../assets";
import { useT } from "../i18n";
import { loadSnapshot, type PlayoffMatch, type Playoffs } from "../snapshot";
import { Notice, Panel, Stat } from "./ui";

/** Раунды сверху вниз: верхняя лента, затем нижняя. */
const UPPER_ROUNDS = ["ubqf", "ubsf", "ubf", "gf"] as const;
const LOWER_ROUNDS = ["lbr1", "lbr2", "lbsf", "lbf"] as const;

// --- геометрия сетки ----------------------------------------------------------

const CARD_W = 208;
// Высота задаётся карточке явно, а не набирается содержимым: по ней считаются
// и места, и линии, и разъехаться они не должны.
const CARD_H = 74;
/** Шаг между соседними сериями раунда. */
const PITCH = 96;
/** Ширина колонки вместе с промежутком под линии. */
const COLUMN = CARD_W + 52;
/** Отступ ленты раундов сверху и зазор между верхней и нижней сетками. */
const HEADER_H = 30;
const BAND_GAP = 56;

interface Placed {
  match: PlayoffMatch;
  x: number;
  y: number;
}

/**
 * Координаты всех четырнадцати мест.
 *
 * Верхняя сетка — обычное дерево: четвертьфиналы с равным шагом, дальше каждая
 * серия посередине между своими. Нижняя идёт лентой под ней: раунд в раунд, а
 * полуфинал и финал — посередине пары. Гранд-финал стоит между лентами: сверху
 * в него приходит верхний финал, снизу — нижний.
 */
function layout(matches: PlayoffMatch[]): { placed: Placed[]; width: number; height: number } {
  const byKey = new Map(matches.map((match) => [match.key, match]));
  const y: Record<string, number> = {};
  const x: Record<string, number> = {};

  const upperTop = HEADER_H;
  ["ubqf1", "ubqf2", "ubqf3", "ubqf4"].forEach((key, index) => {
    x[key] = 0;
    y[key] = upperTop + index * PITCH;
  });
  const middle = (a: string, b: string) => (y[a] + y[b]) / 2;
  x.ubsf1 = COLUMN;
  y.ubsf1 = middle("ubqf1", "ubqf2");
  x.ubsf2 = COLUMN;
  y.ubsf2 = middle("ubqf3", "ubqf4");
  // Финал верхней стоит в одной колонке с финалом нижней — как в компендиуме:
  // так видно, что в гранд-финал они приходят с равных прав.
  x.ubf = COLUMN * 3;
  y.ubf = middle("ubsf1", "ubsf2");

  const lowerTop = upperTop + 3 * PITCH + CARD_H + BAND_GAP + HEADER_H;
  ["lbr1_1", "lbr1_2"].forEach((key, index) => {
    x[key] = 0;
    y[key] = lowerTop + index * PITCH;
  });
  ["lbr2_1", "lbr2_2"].forEach((key, index) => {
    x[key] = COLUMN;
    y[key] = lowerTop + index * PITCH;
  });
  x.lbsf = COLUMN * 2;
  y.lbsf = middle("lbr2_1", "lbr2_2");
  x.lbf = COLUMN * 3;
  y.lbf = y.lbsf;

  // Гранд-финал — между лентами: к нему сходятся оба финала.
  x.gf = COLUMN * 4;
  y.gf = middle("ubf", "lbf");

  const placed = Object.keys(x)
    .map((key) => {
      const match = byKey.get(key);
      return match ? { match, x: x[key], y: y[key] } : null;
    })
    .filter((entry): entry is Placed => entry !== null);

  return {
    placed,
    width: COLUMN * 4 + CARD_W,
    height: Math.max(...Object.values(y)) + CARD_H + 8,
  };
}

/** Кто кого кормит внутри своей ленты — эти связи и рисуются линиями. */
const LINKS: [from: string, to: string][] = [
  ["ubqf1", "ubsf1"],
  ["ubqf2", "ubsf1"],
  ["ubqf3", "ubsf2"],
  ["ubqf4", "ubsf2"],
  ["ubsf1", "ubf"],
  ["ubsf2", "ubf"],
  ["ubf", "gf"],
  ["lbr1_1", "lbr2_1"],
  ["lbr1_2", "lbr2_2"],
  ["lbr2_1", "lbsf"],
  ["lbr2_2", "lbsf"],
  ["lbsf", "lbf"],
  ["lbf", "gf"],
];

/** Линии между местами: горизонталь, вертикаль, горизонталь. */
function connectors(placed: Placed[]): string[] {
  const at = new Map(placed.map((entry) => [entry.match.key, entry]));
  const paths: string[] = [];
  for (const [from, to] of LINKS) {
    const a = at.get(from);
    const b = at.get(to);
    if (!a || !b) continue;
    const x1 = a.x + CARD_W;
    const y1 = a.y + CARD_H / 2;
    const x2 = b.x;
    const y2 = b.y + CARD_H / 2;
    const mid = x1 + (x2 - x1) / 2;
    paths.push(`M ${x1} ${y1} H ${mid} V ${y2} H ${x2}`);
  }
  return paths;
}

function Crest({ name }: { name: string }) {
  const src = teamCrest(name);
  return src ? (
    <img src={src} alt="" className="h-4 w-4 shrink-0 object-contain" />
  ) : (
    <span className="h-4 w-4 shrink-0 rounded-sm bg-[#2a2e3a]" />
  );
}

/** Прогноз на пустое место: кто вероятнее всего его займёт. */
interface Projected {
  name: string;
  chance: number;
}

/** Одна сторона серии: участник со счётом или шансом — либо прогноз на место. */
function Row({
  side,
  projected,
  won,
  lost,
  chance,
  decided,
  title,
}: {
  side: { team_id: number; name: string; score: number } | null;
  projected: Projected | null;
  won: boolean;
  lost: boolean;
  chance: number | null;
  decided: boolean;
  title?: string;
}) {
  const { t } = useT();

  if (!side) {
    // Место ещё не разыграно. Показать «не определён» и уйти было бы честно, но
    // бесполезно: вопрос-то как раз в том, кто сюда дойдёт.
    return (
      <div className="flex flex-1 items-center gap-2 px-2 text-[11px] text-neutral-600" title={title}>
        {projected ? (
          <>
            <span className="opacity-40">
              <Crest name={projected.name} />
            </span>
            <span className="flex-1 truncate text-neutral-500 italic">{projected.name}</span>
            <span className="tabular w-10 text-right text-sky-500/80">
              {Math.round(projected.chance * 100)}%
            </span>
          </>
        ) : (
          <>
            <span className="h-4 w-4 shrink-0 rounded-sm border border-dashed border-[#2a2e3a]" />
            <span className="flex-1">{t("playoff.tbd")}</span>
          </>
        )}
      </div>
    );
  }

  const tone = won ? "text-neutral-100" : lost ? "text-neutral-600" : "text-neutral-300";
  return (
    <div className="flex flex-1 items-center gap-2 px-2 text-[11px]" title={title}>
      <Crest name={side.name} />
      <span className={`flex-1 truncate ${tone}`}>{side.name}</span>
      {decided ? (
        <span className={`tabular w-5 text-right ${won ? "text-[#c8a24a]" : "text-neutral-500"}`}>
          {side.score}
        </span>
      ) : (
        <span className="tabular w-10 text-right text-neutral-400">
          {chance == null ? "—" : `${Math.round(chance * 100)}%`}
        </span>
      )}
    </div>
  );
}

function MatchCard({
  match,
  names,
  onOpen,
}: {
  match: PlayoffMatch;
  names: Map<number, string>;
  onOpen?: (id: number) => void;
}) {
  const { t } = useT();
  const decided = match.winner_id != null;
  const chance = (teamId: number | undefined) =>
    teamId == null ? null : (match.win[String(teamId)] ?? null);

  // Кто сюда дойдёт — только пока участники не определились: у сыгранной серии
  // этот вопрос уже не стоит, а у начатой на него ответила первая карта.
  const reach = useMemo(
    () =>
      Object.entries(match.reach)
        .map(([id, value]) => ({ name: names.get(Number(id)) ?? id, chance: value }))
        .sort((a, b) => b.chance - a.chance),
    [match, names],
  );

  // Прогноз берётся по сторонам, а не по месту целиком. Взять два самых
  // вероятных имени места было бы проще, но так собирается сетка, которой не
  // бывает: команда стоит и в финале верхней, и в полуфинале нижней, куда после
  // выигранного полуфинала верхней уже не попасть. Разводка по фаворитам
  // отвечает на «кто с кем сыграет» одним связным ходом турнира.
  const projectedFor = (side: unknown, index: number): Projected | null => {
    if (side) return null;
    const entry = match.projected?.[index];
    if (!entry) return null;
    const name = names.get(entry.team_id);
    return name ? { name, chance: entry.chance } : null;
  };

  const hint = reach.length
    ? `${t("playoff.reach")}: ${reach
        .slice(0, 4)
        .map((entry) => `${entry.name} ${Math.round(entry.chance * 100)}%`)
        .join(" · ")}`
    : undefined;

  return (
    <div
      className="flex flex-col overflow-hidden rounded border border-[#2a2e3a] bg-[#1a1d24] shadow-sm"
      style={{ height: CARD_H }}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-[#20232c] bg-[#16181e] px-2 py-0.5 text-[10px] text-neutral-600">
        <span className="tabular">{t("playoff.bestOf", { n: match.best_of })}</span>
        {match.match_ids.length > 0 && onOpen && (
          <span className="flex gap-1">
            {match.match_ids.map((id, index) => (
              <button
                key={id}
                onClick={() => onOpen(id)}
                className="text-[#c8a24a] hover:underline"
                title={t("stage.openMap")}
              >
                {index + 1}
              </button>
            ))}
          </span>
        )}
      </div>

      <Row
        side={match.left}
        projected={projectedFor(match.left, 0)}
        won={decided && match.winner_id === match.left?.team_id}
        lost={decided && match.winner_id !== match.left?.team_id}
        chance={chance(match.left?.team_id)}
        decided={decided}
        title={hint}
      />
      <div className="border-t border-[#20232c]" />
      <Row
        side={match.right}
        projected={projectedFor(match.right, 1)}
        won={decided && match.winner_id === match.right?.team_id}
        lost={decided && match.winner_id !== match.right?.team_id}
        chance={chance(match.right?.team_id)}
        decided={decided}
        title={hint}
      />
    </div>
  );
}

/** Дерево сетки: карточки по вычисленным местам плюс линии между ними. */
function Bracket({
  matches,
  names,
  onOpen,
}: {
  matches: PlayoffMatch[];
  names: Map<number, string>;
  onOpen?: (id: number) => void;
}) {
  const { tryT } = useT();
  const { placed, width, height } = useMemo(() => layout(matches), [matches]);
  const paths = useMemo(() => connectors(placed), [placed]);
  const at = new Map(placed.map((entry) => [entry.match.key, entry]));

  /** Подпись раунда — над первой его серией. */
  const headers: { round: string; x: number; y: number }[] = [];
  for (const round of [...UPPER_ROUNDS, ...LOWER_ROUNDS]) {
    const first = placed
      .filter((entry) => entry.match.round === round)
      .sort((a, b) => a.y - b.y)[0];
    if (first) headers.push({ round, x: first.x, y: first.y - HEADER_H + 4 });
  }

  return (
    <div className="overflow-x-auto pb-2">
      <div className="relative" style={{ width, height }}>
        <svg
          className="pointer-events-none absolute inset-0"
          width={width}
          height={height}
          aria-hidden
        >
          {paths.map((d) => (
            <path key={d} d={d} fill="none" stroke="#3a4050" strokeWidth={1} />
          ))}
        </svg>

        {headers.map((header) => (
          <div
            key={header.round}
            className="absolute truncate rounded bg-[#20232c] px-2 py-0.5 text-[11px] tracking-wide text-neutral-300 uppercase"
            style={{ left: header.x, top: header.y, width: CARD_W }}
          >
            {tryT(`playoff.round.${header.round}`, header.round)}
          </div>
        ))}

        {[...at.values()].map((entry) => (
          <div
            key={entry.match.key}
            className="absolute"
            style={{ left: entry.x, top: entry.y, width: CARD_W }}
          >
            <MatchCard match={entry.match} names={names} onOpen={onOpen} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Положение команды в сетке одним словом. */
function Status({ team }: { team: { bracket: string; place: string | null } }) {
  const { t } = useT();
  if (team.place) {
    const gold = team.place === "1";
    return (
      <span
        className={`rounded border px-1.5 py-0.5 text-[10px] tracking-wide uppercase ${
          gold
            ? "border-[#c8a24a] bg-[#1f1c14] text-[#c8a24a]"
            : "border-[#3a3f4b] bg-[#1d2029] text-neutral-400"
        }`}
      >
        {t("playoff.place", { place: team.place })}
      </span>
    );
  }
  const styles =
    team.bracket === "upper"
      ? "border-emerald-800 bg-emerald-950 text-emerald-300"
      : "border-amber-900 bg-amber-950 text-amber-300";
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] tracking-wide uppercase ${styles}`}>
      {t(team.bracket === "upper" ? "playoff.status.upper" : "playoff.status.lower")}
    </span>
  );
}

function heat(probability: number): string {
  if (probability >= 0.3) return "bg-[#c8a24a] text-black";
  if (probability >= 0.15) return "bg-[#8a6f33] text-neutral-100";
  if (probability >= 0.05) return "bg-[#4a3f24] text-neutral-200";
  return "text-neutral-500";
}

export default function PlayoffPanel({ onOpen }: { onOpen?: (id: number) => void }) {
  const { t, tryT, n, d, tp } = useT();
  const [playoffs, setPlayoffs] = useState<Playoffs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSnapshot()
      .then((snapshot) => setPlayoffs(snapshot.playoffs ?? null))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const names = useMemo(
    () => new Map((playoffs?.teams ?? []).map((team) => [team.team_id, team.name])),
    [playoffs],
  );

  if (error) return <Notice kind="error">{error}</Notice>;
  if (loading) return <Notice>{t("playoff.loading")}</Notice>;
  if (!playoffs) return <Notice>{t("playoff.empty")}</Notice>;

  const played = playoffs.matches.filter((match) => match.winner_id != null).length;
  const forecast = playoffs.teams.some((team) => team.champion != null);
  const percentiles = playoffs.points_percentiles ?? {};
  const planByKey = new Map((playoffs.plan ?? []).map((pick) => [pick.key, pick]));

  return (
    <div className="space-y-4">
      <Panel
        title={t("playoff.title")}
        subtitle={
          played
            ? t("playoff.subtitlePlayed", { count: played })
            : t("playoff.subtitleUpcoming", {
                date: playoffs.starts ? d(playoffs.starts) : "—",
              })
        }
      >
        <Bracket matches={playoffs.matches} names={names} onOpen={onOpen} />
        <p className="mt-1 text-[11px] text-neutral-500">{t("playoff.legend")}</p>
        {!forecast && (
          <div className="mt-3">
            <Notice kind="warn">{t("playoff.noForecast")}</Notice>
          </div>
        )}
      </Panel>

      <Panel title={t("playoff.chancesTitle")} subtitle={t("playoff.chancesSubtitle")}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="py-1 text-left">{t("common.team")}</th>
                <th className="py-1 text-center">{t("playoff.recordColumn")}</th>
                <th className="py-1 text-center">{t("playoff.champion")}</th>
                <th className="py-1 text-center">{t("playoff.final")}</th>
                <th className="py-1 text-center">{t("playoff.top4")}</th>
                <th className="py-1 text-center" title={t("playoff.seriesHint")}>
                  {t("playoff.seriesColumn")}
                </th>
                <th className="py-1 text-right">{t("playoff.statusColumn")}</th>
              </tr>
            </thead>
            <tbody>
              {playoffs.teams.map((team) => (
                <tr key={team.team_id} className="border-t border-[#20232c]">
                  <td className="py-1.5">
                    <span className="flex items-center gap-2">
                      <Crest name={team.name} />
                      <span className="text-neutral-200">{team.name}</span>
                    </span>
                  </td>
                  <td className="tabular py-1.5 text-center text-neutral-400">
                    {team.series_won}-{team.series_lost}
                  </td>
                  {[team.champion, team.final, team.top4].map((value, index) => (
                    <td key={index} className="px-1 py-1 text-center">
                      <span
                        className={`tabular inline-block w-14 rounded px-1 py-0.5 ${heat(value ?? 0)}`}
                      >
                        {value == null ? "—" : `${(value * 100).toFixed(1)}%`}
                      </span>
                    </td>
                  ))}
                  <td className="tabular py-1.5 text-center text-neutral-300">
                    {team.expected_series == null ? "—" : n(team.expected_series, 1)}
                  </td>
                  <td className="py-1.5 text-right">
                    <Status team={team} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {playoffs.simulations != null && (
          <p className="mt-2 text-[11px] text-neutral-500">
            {t("playoff.simulationsNote", {
              count: tp("plural.tournaments", playoffs.simulations),
            })}
          </p>
        )}
      </Panel>

      {playoffs.plan && playoffs.plan.length > 0 && (
        <Panel title={t("playoff.planTitle")} subtitle={t("playoff.planSubtitle")}>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label={t("group.expectedPoints")}
              value={n(playoffs.expected_points ?? 0)}
              hint={t("playoff.expectedPointsHint")}
            />
            <Stat
              label={t("group.expectedCorrect")}
              value={(playoffs.expected_correct ?? 0).toFixed(2)}
              hint={t("playoff.expectedCorrectHint")}
            />
            <Stat label={t("group.medianPoints")} value={n(percentiles["50"] ?? 0)} />
            <Stat
              label={t("group.p95")}
              value={n(percentiles["95"] ?? 0)}
              hint={t("group.p95Hint")}
            />
          </div>

          {/* Ставки разложены по раундам, как сама сетка: так их и проставляют
              в компендиуме — сверху вниз, а не списком по алфавиту команд. */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[...UPPER_ROUNDS, ...LOWER_ROUNDS].map((round) => (
              <section key={round} className="space-y-2">
                <header className="rounded border border-[#2a2e3a] bg-[#20232c] px-2 py-1 text-[11px] tracking-wide text-neutral-300 uppercase">
                  {tryT(`playoff.round.${round}`, round)}
                </header>
                {playoffs.matches
                  .filter((match) => match.round === round && planByKey.has(match.key))
                  .sort((a, b) => a.order - b.order)
                  .map((match) => {
                    const pick = planByKey.get(match.key)!;
                    const chance = match.win[String(pick.team_id)] ?? 0;
                    return (
                      <div
                        key={match.key}
                        className="flex items-center gap-2 rounded border border-[#2a2e3a] bg-[#1d2029] px-2 py-2"
                      >
                        <Crest name={pick.name} />
                        <span className="min-w-0 flex-1 truncate text-xs text-neutral-100">
                          {pick.name}
                        </span>
                        <span className="tabular text-[11px] text-neutral-400">
                          {Math.round(chance * 100)}%
                        </span>
                      </div>
                    );
                  })}
              </section>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
