// Миникарта матча с лентой времени.
//
// Позиций героев по тикам в открытом API нет — их отдаёт только разбор самого
// реплея. Зато есть то, ради чего карту и открывают: каждая варда с координатами
// и временем жизни, места смертей в замесах и события вроде вышек и Рошана.
// Этого хватает, чтобы увидеть, как команда держала обзор и где её ловили.
//
// Карта и маркеры — выгрузка интерфейса игры; маркеры чёрные с альфой, поэтому
// красятся CSS-маской, а не пятью копиями файла.

import { useEffect, useMemo, useState } from "react";
import { MAP_IMAGE, MAP_MARKER } from "../assets";
import { useT } from "../i18n";
import { isRadiant, mapPosition, type MatchPlayer, type OpenDotaMatch } from "../opendota";
import { Button } from "./ui";

// Варда живёт фиксированное время, если её не сняли: обсерверная — шесть минут,
// сентри — семь. Точное снятие приходит отдельным логом, но не для каждой.
const OBS_LIFETIME = 360;
const SEN_LIFETIME = 420;

// Смерти в замесе показываются полминуты после его конца: замес длится
// секунды, а маркер, гаснущий мгновенно, невозможно рассмотреть.
const DEATH_TAIL = 30;

// Сколько игровых секунд проходит за один шаг воспроизведения (каждые 100 мс).
const PLAY_STEP = 20;

const RADIANT_COLOR = "#4b9e4b";
const DIRE_COLOR = "#c0453f";

interface Ward {
  key: string;
  kind: "obs" | "sen";
  left: number;
  top: number;
  from: number;
  to: number;
  radiant: boolean;
  who: string;
}

interface Death {
  key: string;
  left: number;
  top: number;
  from: number;
  to: number;
  radiant: boolean;
}

interface FeedEvent {
  time: number;
  kind: "tower" | "racks" | "fort" | "roshan" | "aegis" | "firstblood" | "fight";
  label: string;
  /** Сторона, для которой событие хорошее. */
  radiant?: boolean;
}

export function clock(seconds: number): string {
  const sign = seconds < 0 ? "-" : "";
  const total = Math.abs(Math.round(seconds));
  return `${sign}${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/** `npc_dota_goodguys_tower1_bot` -> `T1 bot`. Слова универсальные для Dota. */
function buildingLabel(key: string): string {
  const name = key.replace(/^npc_dota_(goodguys|badguys)_/, "");
  const tower = /^tower(\d)(?:_(\w+))?$/.exec(name);
  if (tower) return `T${tower[1]}${tower[2] ? ` ${tower[2]}` : ""}`;
  const rax = /^(melee|range)_rax_(\w+)$/.exec(name);
  if (rax) return `${rax[1] === "melee" ? "Melee" : "Range"} rax ${rax[2]}`;
  if (name === "fort") return "Ancient";
  return name.replace(/_/g, " ");
}

export default function MatchMap({
  match,
  playerName,
}: {
  match: OpenDotaMatch;
  playerName: (player: MatchPlayer) => string;
}) {
  const { t, n } = useT();
  const [time, setTime] = useState(match.duration);
  const [playing, setPlaying] = useState(false);
  // Режим «вся игра» — карта вардинга целиком, она же самый полезный вид:
  // видно, какие точки команда закрывает всегда, а какие не закрывает никогда.
  const [whole, setWhole] = useState(true);

  const wards = useMemo(() => {
    const out: Ward[] = [];
    for (const player of match.players) {
      const radiant = isRadiant(player);
      const who = playerName(player);
      const logs = [
        ["obs", player.obs_log, player.obs_left_log, OBS_LIFETIME],
        ["sen", player.sen_log, player.sen_left_log, SEN_LIFETIME],
      ] as const;

      for (const [kind, log, leftLog, lifetime] of logs) {
        // Снятие сходится с постановкой по ehandle — это идентификатор
        // сущности, времени в самой записи о постановке нет.
        const removed = new Map(
          (leftLog ?? []).map((entry) => [entry.ehandle ?? -1, entry.time]),
        );
        for (const entry of log ?? []) {
          const { left, top } = mapPosition(entry.x, entry.y);
          out.push({
            key: `${kind}-${player.player_slot}-${entry.time}-${entry.x}-${entry.y}`,
            kind,
            left,
            top,
            from: entry.time,
            to: removed.get(entry.ehandle ?? -1) ?? entry.time + lifetime,
            radiant,
            who,
          });
        }
      }
    }
    return out;
  }, [match, playerName]);

  const deaths = useMemo(() => {
    const out: Death[] = [];
    (match.teamfights ?? []).forEach((fight, index) => {
      (fight.players ?? []).forEach((player, slot) => {
        for (const [x, column] of Object.entries(player.deaths_pos ?? {})) {
          for (const y of Object.keys(column)) {
            const { left, top } = mapPosition(Number(x), Number(y));
            out.push({
              key: `death-${index}-${slot}-${x}-${y}`,
              left,
              top,
              from: fight.start,
              to: (fight.end ?? fight.start) + DEATH_TAIL,
              // Порядок игроков в замесе тот же, что в матче: первые пять — Radiant.
              radiant: slot < 5,
            });
          }
        }
      });
    });
    return out;
  }, [match]);

  const events = useMemo(() => {
    const out: FeedEvent[] = [];
    for (const objective of match.objectives ?? []) {
      const key = String(objective.key ?? "");
      switch (objective.type) {
        case "building_kill": {
          const lost = key.includes("goodguys");
          const kind = key.includes("rax") ? "racks" : key.includes("fort") ? "fort" : "tower";
          out.push({ time: objective.time, kind, label: buildingLabel(key), radiant: !lost });
          break;
        }
        case "CHAT_MESSAGE_ROSHAN_KILL":
          out.push({
            time: objective.time,
            kind: "roshan",
            label: t("event.roshan"),
            radiant: objective.team === 2,
          });
          break;
        case "CHAT_MESSAGE_AEGIS":
          out.push({ time: objective.time, kind: "aegis", label: t("event.aegis") });
          break;
        case "CHAT_MESSAGE_FIRSTBLOOD":
          out.push({ time: objective.time, kind: "firstblood", label: t("event.firstBlood") });
          break;
      }
    }
    for (const fight of match.teamfights ?? []) {
      if ((fight.deaths ?? 0) >= 3) {
        out.push({
          time: fight.start,
          kind: "fight",
          label: t("event.fight", { n: fight.deaths ?? 0 }),
        });
      }
    }
    return out.sort((a, b) => a.time - b.time);
  }, [match, t]);

  useEffect(() => {
    if (!playing || whole) return;
    const timer = window.setInterval(
      () => setTime((current) => Math.min(match.duration, current + PLAY_STEP)),
      100,
    );
    return () => window.clearInterval(timer);
  }, [playing, whole, match.duration]);

  // Останов на конце игры — отдельным эффектом: менять чужое состояние внутри
  // вычислителя setTime нельзя, React такое обновление теряет.
  useEffect(() => {
    if (playing && time >= match.duration) setPlaying(false);
  }, [playing, time, match.duration]);

  // Кнопка «пуск» с конца игры перематывает в начало — иначе она не делает
  // ничего и выглядит сломанной.
  const play = () => {
    if (time >= match.duration) setTime(0);
    setPlaying((value) => !value);
  };

  const visible = (from: number, to: number) => whole || (from <= time && to >= time);
  const shownWards = wards.filter((ward) => visible(ward.from, ward.to));
  const obsAlive = shownWards.filter((ward) => ward.kind === "obs").length;
  const senAlive = shownWards.length - obsAlive;

  if (!wards.length && !deaths.length) return null;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,18rem)]">
      <div>
        {/* Исходник миникарты — 400 пикселей: тянуть её на всю ширину панели
            значит показать мыло, поэтому ширина ограничена. */}
        <div
          className="relative aspect-square w-full max-w-[560px] overflow-hidden rounded border border-[#2a2e3a] bg-[#0f1115] bg-cover"
          style={{ backgroundImage: `url(${MAP_IMAGE})` }}
        >
          {deaths.map(
            (death) =>
              visible(death.from, death.to) && (
                <span
                  key={death.key}
                  className="absolute block h-4 w-4 -translate-x-1/2 -translate-y-1/2 opacity-80"
                  style={{
                    left: `${death.left}%`,
                    top: `${death.top}%`,
                    backgroundColor: death.radiant ? RADIANT_COLOR : DIRE_COLOR,
                    WebkitMaskImage: `url(${MAP_MARKER.death})`,
                    maskImage: `url(${MAP_MARKER.death})`,
                    WebkitMaskSize: "contain",
                    maskSize: "contain",
                  }}
                />
              ),
          )}

          {shownWards.map((ward) => (
            <span
              key={ward.key}
              title={`${ward.who} · ${clock(ward.from)}–${clock(ward.to)}`}
              className={`absolute block -translate-x-1/2 -translate-y-1/2 ${
                ward.kind === "obs" ? "h-3.5 w-3.5" : "h-2.5 w-2.5 rounded-full border"
              }`}
              style={
                ward.kind === "obs"
                  ? {
                      left: `${ward.left}%`,
                      top: `${ward.top}%`,
                      backgroundColor: ward.radiant ? RADIANT_COLOR : DIRE_COLOR,
                      WebkitMaskImage: `url(${MAP_MARKER.ward})`,
                      maskImage: `url(${MAP_MARKER.ward})`,
                      WebkitMaskSize: "contain",
                      maskSize: "contain",
                    }
                  : {
                      left: `${ward.left}%`,
                      top: `${ward.top}%`,
                      borderColor: ward.radiant ? RADIANT_COLOR : DIRE_COLOR,
                      backgroundColor: "#0f1115aa",
                    }
              }
            />
          ))}
        </div>

        <div className="mt-3 flex max-w-[560px] flex-wrap items-center gap-3">
          <Button variant="ghost" onClick={() => setWhole((value) => !value)}>
            {whole ? t("map.modeMoment") : t("map.modeWhole")}
          </Button>
          {!whole && (
            <>
              <Button onClick={play}>
                {playing ? t("map.pause") : t("map.play")}
              </Button>
              <span className="tabular w-14 text-sm text-neutral-200">{clock(time)}</span>
              <input
                type="range"
                min={0}
                max={match.duration}
                step={5}
                value={time}
                onChange={(e) => setTime(Number(e.target.value))}
                className="h-1 min-w-[12rem] flex-1 cursor-pointer accent-[#c8a24a]"
                aria-label={t("map.slider")}
              />
            </>
          )}
        </div>

        <p className="mt-2 text-[11px] text-neutral-500">
          {whole ? t("map.wholeHint") : t("map.momentHint")}
        </p>
      </div>

      <div className="space-y-3">
        <div className="rounded border border-[#20232c] bg-[#1a1d24] p-3 text-[11px]">
          <p className="mb-2 tracking-wide text-neutral-500 uppercase">{t("map.legend")}</p>
          <div className="space-y-1 text-neutral-400">
            <p>
              <span className="mr-2 inline-block h-2 w-2 rounded-full align-middle" style={{ backgroundColor: RADIANT_COLOR }} />
              Radiant
              <span className="mx-2 inline-block h-2 w-2 rounded-full align-middle" style={{ backgroundColor: DIRE_COLOR }} />
              Dire
            </p>
            <p>{t("map.legendObs", { n: obsAlive })}</p>
            <p>{t("map.legendSen", { n: senAlive })}</p>
            <p>{t("map.legendDeath", { n: n(deaths.length) })}</p>
          </div>
        </div>

        {events.length > 0 && (
          <div className="rounded border border-[#20232c] bg-[#1a1d24] p-3">
            <p className="mb-2 text-[11px] tracking-wide text-neutral-500 uppercase">
              {t("map.events")}
            </p>
            <div className="max-h-[22rem] space-y-0.5 overflow-y-auto pr-1">
              {events.map((event, index) => (
                <button
                  key={`${event.time}-${event.kind}-${index}`}
                  onClick={() => {
                    setWhole(false);
                    setPlaying(false);
                    setTime(event.time);
                  }}
                  className={`flex w-full items-baseline gap-2 rounded px-1 py-0.5 text-left text-[11px] hover:bg-[#20232c] ${
                    !whole && Math.abs(event.time - time) <= 20 ? "bg-[#20232c]" : ""
                  }`}
                >
                  <span className="tabular w-10 shrink-0 text-neutral-500">
                    {clock(event.time)}
                  </span>
                  <span
                    className="truncate"
                    style={{
                      color:
                        event.radiant === undefined
                          ? "#a3a3a3"
                          : event.radiant
                            ? RADIANT_COLOR
                            : DIRE_COLOR,
                    }}
                  >
                    {event.label}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
