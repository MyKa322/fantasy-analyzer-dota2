// Сетка плей-офф: восемь команд, double elimination, четырнадцать серий.
//
// Сетка рисуется целиком заранее — как и групповая, — но по другой причине.
// В Swiss число мест выводится из формата, здесь оно задано объявленной сеткой:
// четвертьфиналы известны, остальные места ждут участников. Пустое место — это
// не отсутствие данных, а нерешённая серия, и у него есть что показать: кто
// туда дойдёт и с какой вероятностью.
//
// Второе, ради чего страница существует: у каждой серии два разных вопроса —
// «кто здесь окажется» и «кто здесь выиграет». Для четвертьфинала первый ответ
// тривиален, для гранд-финала — нет, и путать их нельзя.

import { useEffect, useMemo, useState } from "react";
import { teamCrest } from "../assets";
import { useT } from "../i18n";
import { loadSnapshot, type PlayoffMatch, type Playoffs } from "../snapshot";
import { Notice, Panel, Stat } from "./ui";

/** Раунды сверху вниз: верхняя лента, затем нижняя. */
const UPPER_ROUNDS = ["ubqf", "ubsf", "ubf", "gf"] as const;
const LOWER_ROUNDS = ["lbr1", "lbr2", "lbsf", "lbf"] as const;

function Crest({ name }: { name: string }) {
  const src = teamCrest(name);
  return src ? (
    <img src={src} alt="" className="h-4 w-4 shrink-0 object-contain" />
  ) : (
    <span className="h-4 w-4 shrink-0 rounded-sm bg-[#2a2e3a]" />
  );
}

/** Одна сторона серии: команда со счётом или с вероятностью победы. */
function Row({
  side,
  won,
  lost,
  chance,
  decided,
}: {
  side: { team_id: number; name: string; score: number } | null;
  won: boolean;
  lost: boolean;
  chance: number | null;
  decided: boolean;
}) {
  const { t } = useT();

  if (!side) {
    return (
      <div className="flex items-center gap-2 px-2 py-1.5 text-[11px] text-neutral-600">
        <span className="h-4 w-4 shrink-0 rounded-sm border border-dashed border-[#2a2e3a]" />
        <span className="flex-1">{t("playoff.tbd")}</span>
      </div>
    );
  }

  const tone = won ? "text-neutral-100" : lost ? "text-neutral-600" : "text-neutral-300";
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 text-[11px]">
      <Crest name={side.name} />
      <span className={`flex-1 truncate ${tone}`}>{side.name}</span>
      {decided ? (
        <span className={`tabular w-5 text-right ${won ? "text-[#c8a24a]" : "text-neutral-500"}`}>
          {side.score}
        </span>
      ) : (
        <span className="tabular w-10 text-right text-neutral-500">
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
  const reach = useMemo(() => {
    if (match.left && match.right) return [];
    return Object.entries(match.reach)
      .map(([id, value]) => ({ name: names.get(Number(id)) ?? id, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 3);
  }, [match, names]);

  return (
    <div className="rounded border border-[#2a2e3a] bg-[#1a1d24]">
      <div className="flex items-center justify-between border-b border-[#20232c] px-2 py-1 text-[10px] text-neutral-600">
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
        won={decided && match.winner_id === match.left?.team_id}
        lost={decided && match.winner_id !== match.left?.team_id}
        chance={chance(match.left?.team_id)}
        decided={decided}
      />
      <div className="border-t border-[#20232c]" />
      <Row
        side={match.right}
        won={decided && match.winner_id === match.right?.team_id}
        lost={decided && match.winner_id !== match.right?.team_id}
        chance={chance(match.right?.team_id)}
        decided={decided}
      />

      {reach.length > 0 && (
        <div className="border-t border-[#20232c] px-2 py-1 text-[10px] text-neutral-500">
          <span className="text-neutral-600">{t("playoff.reach")}: </span>
          {reach.map((entry, index) => (
            <span key={entry.name} className="whitespace-nowrap">
              {index > 0 && " · "}
              {entry.name}{" "}
              <span className="tabular text-neutral-400">
                {Math.round(entry.value * 100)}%
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Bracket({
  rounds,
  matches,
  names,
  onOpen,
}: {
  rounds: readonly string[];
  matches: PlayoffMatch[];
  names: Map<number, string>;
  onOpen?: (id: number) => void;
}) {
  const { tryT } = useT();
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {rounds.map((round) => (
        <section key={round} className="space-y-2">
          <header className="rounded border border-[#2a2e3a] bg-[#20232c] px-2 py-1 text-[11px] tracking-wide text-neutral-300 uppercase">
            {tryT(`playoff.round.${round}`, round)}
          </header>
          {matches
            .filter((match) => match.round === round)
            .sort((a, b) => a.order - b.order)
            .map((match) => (
              <MatchCard key={match.key} match={match} names={names} onOpen={onOpen} />
            ))}
        </section>
      ))}
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
        <div className="space-y-4">
          <Bracket
            rounds={UPPER_ROUNDS}
            matches={playoffs.matches}
            names={names}
            onOpen={onOpen}
          />
          <Bracket
            rounds={LOWER_ROUNDS}
            matches={playoffs.matches}
            names={names}
            onOpen={onOpen}
          />
        </div>
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
