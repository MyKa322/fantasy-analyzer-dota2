// Миникарта матча: обзор, смерти и события.
//
// Позиций героев по тикам в открытом API нет — их отдаёт только разбор самого
// реплея. Зато есть то, ради чего карту и открывают: каждая варда с
// координатами и временем жизни, места смертей в замесах и события целей.
//
// Главное решение здесь — не рисовать всё сразу. Сотня маркеров на карте в 400
// пикселей превращается в кашу, поэтому по умолчанию включён один слой
// (обсерверные варды), а остальное добавляется чипами: слои, стороны и
// конкретный игрок. Наведение на варду показывает её радиус обзора — то, ради
// чего её и ставили.
//
// Карта и маркеры — выгрузка интерфейса игры; маркеры чёрные с альфой, поэтому
// красятся CSS-маской, а не пятью копиями файла.

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { MAP_IMAGE, MAP_MARKER, heroIcon } from "../assets";
import { useT } from "../i18n";
import { mapPosition, type OpenDotaMatch } from "../opendota";

// Варда живёт фиксированное время, если её не сняли: обсерверная — шесть минут,
// сентри — семь. Точное снятие приходит отдельным логом, но не для каждой.
const OBS_LIFETIME = 360;
const SEN_LIFETIME = 420;

// Радиус обзора в долях ширины карты. Играбельная часть — 128 клеток сетки по
// 128 игровых единиц: обсерверная видит на 1600 единиц, то есть на 12,5 клетки,
// сентри даёт истинное зрение на 900.
const OBS_RADIUS = (1600 / 128 / 128) * 100;
const SEN_RADIUS = (900 / 128 / 128) * 100;

// Смерти в замесе показываются полминуты после его конца: замес длится
// секунды, а маркер, гаснущий мгновенно, невозможно рассмотреть.
const DEATH_TAIL = 30;

// Сколько игровых секунд проходит за один шаг воспроизведения (каждые 100 мс).
const PLAY_STEP = 20;

const RADIANT_COLOR = "#4b9e4b";
const DIRE_COLOR = "#c0453f";

type Layer = "obs" | "sen" | "death";
type Side = "radiant" | "dire";

/** Игрок матча в том виде, в каком его показывает карта. */
export interface MapPlayer {
  slot: number;
  name: string;
  hero: string;
  heroId: number;
  radiant: boolean;
}

interface Ward {
  key: string;
  kind: "obs" | "sen";
  left: number;
  top: number;
  from: number;
  to: number;
  slot: number;
  radiant: boolean;
  /** Сняли раньше срока — значит, её нашли и уничтожили. */
  destroyed: boolean;
}

interface Death {
  key: string;
  left: number;
  top: number;
  from: number;
  to: number;
  slot: number;
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

const EVENT_ICON: Record<FeedEvent["kind"], string> = {
  tower: MAP_MARKER.tower,
  racks: MAP_MARKER.racks,
  fort: MAP_MARKER.ancient,
  roshan: MAP_MARKER.roshan,
  aegis: MAP_MARKER.roshan,
  firstblood: MAP_MARKER.death,
  fight: MAP_MARKER.death,
};

/** Чип-переключатель: подпись, счётчик и цвет включённого состояния. */
function Chip({
  active,
  color,
  onClick,
  children,
}: {
  active: boolean;
  color?: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] transition ${
        active
          ? "border-transparent bg-[#20232c] text-neutral-100"
          : "border-[#20232c] text-neutral-500 hover:text-neutral-300"
      }`}
      style={active && color ? { borderColor: color } : undefined}
    >
      {children}
    </button>
  );
}

/** Маска-иконка из выгрузки интерфейса, покрашенная в нужный цвет. */
function glyph(url: string, color: string, size: number): CSSProperties {
  return {
    width: size,
    height: size,
    backgroundColor: color,
    WebkitMaskImage: `url(${url})`,
    maskImage: `url(${url})`,
    WebkitMaskSize: "contain",
    maskSize: "contain",
    WebkitMaskRepeat: "no-repeat",
    maskRepeat: "no-repeat",
  };
}

export default function MatchMap({
  match,
  roster,
}: {
  match: OpenDotaMatch;
  roster: MapPlayer[];
}) {
  const { t, n } = useT();
  const [time, setTime] = useState(match.duration);
  const [playing, setPlaying] = useState(false);
  const [whole, setWhole] = useState(true);
  // По умолчанию виден один слой: карта вардинга — то, ради чего сюда заходят.
  // Сентри и смерти включаются чипами, иначе на старте каша из ста маркеров.
  const [layers, setLayers] = useState<Layer[]>(["obs"]);
  const [sides, setSides] = useState<Side[]>(["radiant", "dire"]);
  const [focus, setFocus] = useState<number | null>(null);
  const [coverage, setCoverage] = useState(false);
  const [hover, setHover] = useState<Ward | null>(null);

  const bySlot = useMemo(
    () => new Map(roster.map((player) => [player.slot, player])),
    [roster],
  );

  const wards = useMemo(() => {
    const out: Ward[] = [];
    for (const player of match.players) {
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
          const gone = removed.get(entry.ehandle ?? -1);
          out.push({
            key: `${kind}-${player.player_slot}-${entry.time}-${entry.x}-${entry.y}`,
            kind,
            left,
            top,
            from: entry.time,
            to: gone ?? entry.time + lifetime,
            slot: player.player_slot,
            radiant: player.player_slot < 128,
            // Пять секунд запаса: варда, снятая на последней секунде жизни,
            // это не находка вражеского саппорта.
            destroyed: gone != null && gone < entry.time + lifetime - 5,
          });
        }
      }
    }
    return out;
  }, [match]);

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
              slot: slot < 5 ? slot : slot + 123,
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

  const play = () => {
    if (time >= match.duration) setTime(0);
    setPlaying((value) => !value);
  };

  const toggle = <T,>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

  const alive = (from: number, to: number) => whole || (from <= time && to >= time);
  const sideOn = (radiant: boolean) => sides.includes(radiant ? "radiant" : "dire");
  const focused = (slot: number) => focus === null || focus === slot;

  const shownWards = wards.filter(
    (ward) =>
      layers.includes(ward.kind) && sideOn(ward.radiant) && focused(ward.slot) && alive(ward.from, ward.to),
  );
  const shownDeaths = deaths.filter(
    (death) =>
      layers.includes("death") && sideOn(death.radiant) && alive(death.from, death.to),
  );

  // Сводка по вардам — то, за чем на карту смотрят второй раз: сколько
  // поставили, сколько из них нашли и сколько варда в среднем прожила.
  const summary = useMemo(() => {
    const side = (radiant: boolean) => {
      const own = wards.filter((ward) => ward.radiant === radiant);
      const obs = own.filter((ward) => ward.kind === "obs");
      const lifetimes = obs.map((ward) => ward.to - ward.from);
      return {
        obs: obs.length,
        sen: own.length - obs.length,
        destroyed: own.filter((ward) => ward.destroyed).length,
        lifetime: lifetimes.length
          ? lifetimes.reduce((sum, value) => sum + value, 0) / lifetimes.length
          : 0,
        deaths: deaths.filter((death) => death.radiant === radiant).length,
      };
    };
    return { radiant: side(true), dire: side(false) };
  }, [wards, deaths]);

  const counts = {
    obs: wards.filter((ward) => ward.kind === "obs").length,
    sen: wards.filter((ward) => ward.kind === "sen").length,
    death: deaths.length,
  };

  if (!wards.length && !deaths.length) return null;

  const hoverColor = hover?.radiant ? RADIANT_COLOR : DIRE_COLOR;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)]">
      <div>
        {/* Режим и время: сегментами, а не одной кнопкой-перевёртышем —
            по кнопке «Вся игра» невозможно понять, включена она или предлагается. */}
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <div className="flex overflow-hidden rounded border border-[#2a2e3a]">
            {([
              [true, t("map.modeWhole")],
              [false, t("map.modeTime")],
            ] as const).map(([value, label]) => (
              <button
                key={String(value)}
                onClick={() => {
                  setWhole(value);
                  if (value) setPlaying(false);
                }}
                className={`px-3 py-1 text-[11px] transition ${
                  whole === value
                    ? "bg-[#c8a24a] text-black"
                    : "text-neutral-400 hover:text-neutral-100"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {!whole && (
            <>
              <button
                onClick={play}
                className="rounded border border-[#2a2e3a] px-3 py-1 text-[11px] text-neutral-200 hover:border-[#c8a24a]"
              >
                {playing ? t("map.pause") : t("map.play")}
              </button>
              <span className="tabular w-12 text-sm text-[#c8a24a]">{clock(time)}</span>
            </>
          )}
        </div>

        {!whole && (
          <div className="relative mb-3">
            <input
              type="range"
              min={0}
              max={match.duration}
              step={5}
              value={time}
              onChange={(e) => setTime(Number(e.target.value))}
              className="h-1 w-full cursor-pointer accent-[#c8a24a]"
              aria-label={t("map.slider")}
            />
            {/* Насечки событий: по ним видно, когда что-то происходило, и можно
                прыгнуть в нужную минуту, не перебирая ползунок вслепую. */}
            <div className="pointer-events-none absolute inset-x-0 top-4 h-3">
              {events.map((event, index) => (
                <span
                  key={`tick-${event.time}-${index}`}
                  className="pointer-events-auto absolute top-0 h-3 w-px cursor-pointer"
                  style={{
                    left: `${(event.time / Math.max(1, match.duration)) * 100}%`,
                    backgroundColor:
                      event.radiant === undefined
                        ? "#6b7280"
                        : event.radiant
                          ? RADIANT_COLOR
                          : DIRE_COLOR,
                  }}
                  title={`${clock(event.time)} · ${event.label}`}
                  onClick={() => {
                    setPlaying(false);
                    setTime(event.time);
                  }}
                />
              ))}
            </div>
          </div>
        )}

        <div
          className="relative aspect-square w-full overflow-hidden rounded border border-[#2a2e3a] bg-[#0f1115] bg-cover"
          style={{ backgroundImage: `url(${MAP_IMAGE})` }}
        >
          {/* Подписи сторон: без них человек, не игравший в Dota, не поймёт,
              чей угол какой. */}
          <span
            className="pointer-events-none absolute bottom-1 left-1.5 text-[10px] tracking-wide uppercase opacity-70"
            style={{ color: RADIANT_COLOR }}
          >
            Radiant
          </span>
          <span
            className="pointer-events-none absolute top-1 right-1.5 text-[10px] tracking-wide uppercase opacity-70"
            style={{ color: DIRE_COLOR }}
          >
            Dire
          </span>

          {/* Зона обзора: у всех вард сразу по кнопке или у одной под курсором. */}
          {shownWards.map((ward) => {
            const shown = coverage || hover?.key === ward.key;
            if (!shown) return null;
            const radius = ward.kind === "obs" ? OBS_RADIUS : SEN_RADIUS;
            const color = ward.radiant ? RADIANT_COLOR : DIRE_COLOR;
            return (
              <span
                key={`area-${ward.key}`}
                className="pointer-events-none absolute rounded-full"
                style={{
                  left: `${ward.left}%`,
                  top: `${ward.top}%`,
                  width: `${radius * 2}%`,
                  height: `${radius * 2}%`,
                  transform: "translate(-50%, -50%)",
                  backgroundColor: `${color}${hover?.key === ward.key ? "44" : "1f"}`,
                  border: `1px solid ${color}${hover?.key === ward.key ? "aa" : "33"}`,
                }}
              />
            );
          })}

          {shownDeaths.map((death) => (
            <span
              key={death.key}
              className="pointer-events-none absolute block -translate-x-1/2 -translate-y-1/2 opacity-80"
              style={{
                left: `${death.left}%`,
                top: `${death.top}%`,
                ...glyph(MAP_MARKER.death, death.radiant ? RADIANT_COLOR : DIRE_COLOR, 15),
              }}
            />
          ))}

          {shownWards.map((ward) => {
            const color = ward.radiant ? RADIANT_COLOR : DIRE_COLOR;
            return (
              <button
                key={ward.key}
                onMouseEnter={() => setHover(ward)}
                onMouseLeave={() => setHover((current) => (current?.key === ward.key ? null : current))}
                className="absolute -translate-x-1/2 -translate-y-1/2 cursor-help"
                style={{ left: `${ward.left}%`, top: `${ward.top}%` }}
                aria-label={`${bySlot.get(ward.slot)?.hero ?? ""} ${clock(ward.from)}`}
              >
                {ward.kind === "obs" ? (
                  <span
                    className="block"
                    style={{
                      ...glyph(MAP_MARKER.ward, color, 15),
                      filter: hover?.key === ward.key ? "brightness(1.6)" : undefined,
                    }}
                  />
                ) : (
                  <span
                    className="block rounded-full border-2"
                    style={{
                      width: 9,
                      height: 9,
                      borderColor: color,
                      backgroundColor: "#0f1115cc",
                    }}
                  />
                )}
                {/* Снесённая варда помечается крестиком: это не «истекла», а
                    «нашли и убили» — совсем другой факт про обзор. */}
                {ward.destroyed && (
                  <span
                    className="pointer-events-none absolute -top-1 -right-1 text-[9px] leading-none"
                    style={{ color }}
                  >
                    ×
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Строка под картой: что под курсором, либо подсказка. */}
        <p className="mt-2 min-h-[1.25rem] text-[11px]">
          {hover ? (
            // Тип варды показывает её же значок, а не слово: подпись под картой
            // и так длинная, а глиф читается быстрее.
            <span className="inline-flex items-center gap-1.5" style={{ color: hoverColor }}>
              {hover.kind === "obs" ? (
                <span style={glyph(MAP_MARKER.ward, hoverColor, 12)} />
              ) : (
                <span
                  className="inline-block rounded-full border-2"
                  style={{ width: 9, height: 9, borderColor: hoverColor }}
                />
              )}
              {bySlot.get(hover.slot)?.hero ?? "—"} · {clock(hover.from)}–{clock(hover.to)}
              {hover.destroyed && ` · ${t("map.destroyedOne")}`}
            </span>
          ) : (
            <span className="text-neutral-500">
              {whole ? t("map.wholeHint") : t("map.momentHint")}
            </span>
          )}
        </p>
      </div>

      <div className="space-y-3">
        <div className="rounded border border-[#20232c] bg-[#1a1d24] p-3">
          <p className="mb-2 text-[11px] tracking-wide text-neutral-500 uppercase">
            {t("map.layers")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {([
              ["obs", MAP_MARKER.ward, t("map.wardObs"), counts.obs],
              ["sen", null, t("map.wardSen"), counts.sen],
              ["death", MAP_MARKER.death, t("map.deaths"), counts.death],
            ] as const).map(([layer, icon, label, count]) => (
              <Chip
                key={layer}
                active={layers.includes(layer)}
                color="#c8a24a"
                onClick={() => setLayers((current) => toggle(current, layer))}
              >
                {icon ? (
                  <span style={glyph(icon, "currentColor", 11)} />
                ) : (
                  <span className="inline-block h-2 w-2 rounded-full border border-current" />
                )}
                {label}
                <span className="tabular text-neutral-500">{count}</span>
              </Chip>
            ))}
            <Chip active={coverage} color="#c8a24a" onClick={() => setCoverage((v) => !v)}>
              {t("map.coverage")}
            </Chip>
          </div>

          <p className="mt-3 mb-2 text-[11px] tracking-wide text-neutral-500 uppercase">
            {t("map.sides")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {([
              ["radiant", "Radiant", RADIANT_COLOR],
              ["dire", "Dire", DIRE_COLOR],
            ] as const).map(([side, label, color]) => (
              <Chip
                key={side}
                active={sides.includes(side)}
                color={color}
                onClick={() => setSides((current) => toggle(current, side))}
              >
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                {label}
              </Chip>
            ))}
          </div>

          <p className="mt-3 mb-2 text-[11px] tracking-wide text-neutral-500 uppercase">
            {t("map.players")}
          </p>
          <div className="flex flex-wrap gap-1">
            {roster.map((player) => {
              const icon = heroIcon(player.heroId);
              const active = focus === player.slot;
              return (
                <button
                  key={player.slot}
                  onClick={() => setFocus(active ? null : player.slot)}
                  title={`${player.name} · ${player.hero}`}
                  className={`overflow-hidden rounded-sm border transition ${
                    active ? "opacity-100" : "opacity-60 hover:opacity-100"
                  }`}
                  style={{ borderColor: active ? (player.radiant ? RADIANT_COLOR : DIRE_COLOR) : "#20232c" }}
                >
                  {icon ? (
                    <img src={icon} alt={player.hero} className="h-6 w-10 object-cover" />
                  ) : (
                    <span className="block h-6 w-10 text-[9px] text-neutral-500">{player.hero}</span>
                  )}
                </button>
              );
            })}
            {focus !== null && (
              <Chip active onClick={() => setFocus(null)}>
                {t("map.allPlayers")}
              </Chip>
            )}
          </div>
        </div>

        <div className="rounded border border-[#20232c] bg-[#1a1d24] p-3">
          <p className="mb-2 text-[11px] tracking-wide text-neutral-500 uppercase">
            {t("map.summary")}
          </p>
          <table className="w-full text-[11px]">
            <thead className="text-neutral-500">
              <tr>
                <th className="text-left font-normal"> </th>
                <th className="text-right font-normal">{t("map.wardObs")}</th>
                <th className="text-right font-normal">{t("map.wardSen")}</th>
                <th className="text-right font-normal">{t("map.destroyed")}</th>
                <th className="text-right font-normal">{t("map.lifetime")}</th>
              </tr>
            </thead>
            <tbody>
              {([
                ["Radiant", RADIANT_COLOR, summary.radiant],
                ["Dire", DIRE_COLOR, summary.dire],
              ] as const).map(([label, color, row]) => (
                <tr key={label} className="border-t border-[#20232c]">
                  <td className="py-1" style={{ color }}>
                    {label}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-300">{n(row.obs)}</td>
                  <td className="tabular py-1 text-right text-neutral-300">{n(row.sen)}</td>
                  <td className="tabular py-1 text-right text-neutral-400">{n(row.destroyed)}</td>
                  <td className="tabular py-1 text-right text-neutral-400">
                    {clock(row.lifetime)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[10px] text-neutral-600">{t("map.summaryHint")}</p>
        </div>

        {events.length > 0 && (
          <div className="rounded border border-[#20232c] bg-[#1a1d24] p-3">
            <p className="mb-2 text-[11px] tracking-wide text-neutral-500 uppercase">
              {t("map.events")}
            </p>
            <div className="max-h-64 space-y-0.5 overflow-y-auto pr-1">
              {events.map((event, index) => {
                const color =
                  event.radiant === undefined
                    ? "#a3a3a3"
                    : event.radiant
                      ? RADIANT_COLOR
                      : DIRE_COLOR;
                return (
                  <button
                    key={`${event.time}-${event.kind}-${index}`}
                    onClick={() => {
                      setWhole(false);
                      setPlaying(false);
                      setTime(event.time);
                    }}
                    className={`flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-[11px] hover:bg-[#20232c] ${
                      !whole && Math.abs(event.time - time) <= 20 ? "bg-[#20232c]" : ""
                    }`}
                  >
                    <span className="tabular w-9 shrink-0 text-neutral-500">
                      {clock(event.time)}
                    </span>
                    <span className="shrink-0" style={glyph(EVENT_ICON[event.kind], color, 12)} />
                    <span className="truncate" style={{ color }}>
                      {event.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
