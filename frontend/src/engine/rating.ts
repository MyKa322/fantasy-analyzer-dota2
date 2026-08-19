// Glicko-2 в браузере — порт `backend/app/analytics/{glicko2,rating}.py`.
//
// Копия математики появилась не от хорошей жизни: страница даёт выбрать основу
// оценки (какие турниры и какой период идут в рейтинг), а под каждый выбор
// нужен свой пересчёт. Гонять его на сервере нельзя — сайт статический, сервера
// нет вовсе. Поэтому сырьё (исходы карт) выкладывается файлом, а считает
// браузер.
//
// Раз копий две, они обязаны сходиться: при полной основе рейтинг здесь должен
// совпасть с тем, что лежит в снапшоте, вплоть до десятых. Это и есть проверка
// порта — она делается на реальных данных, а не на выдуманном примере.

export const SCALE = 173.7178;
export const DEFAULT_RATING = 1500;
export const DEFAULT_RD = 350;
export const DEFAULT_VOLATILITY = 0.06;
export const DEFAULT_TAU = 0.5;
const CONVERGENCE_EPSILON = 1e-6;

export interface Rating {
  rating: number;
  rd: number;
  volatility: number;
}

export const INITIAL: Rating = {
  rating: DEFAULT_RATING,
  rd: DEFAULT_RD,
  volatility: DEFAULT_VOLATILITY,
};

/** Одна карта: когда сыграна, на каком турнире, кто с кем и кто победил. */
export interface MapResult {
  /** Unix-время начала, в секундах. */
  ts: number;
  /** id турнира; 0 — турнир неизвестен. */
  league: number;
  radiant: number;
  dire: number;
  radiantWin: boolean;
}

const mu = (r: Rating) => (r.rating - DEFAULT_RATING) / SCALE;
const phi = (r: Rating) => r.rd / SCALE;

function g(value: number): number {
  return 1 / Math.sqrt(1 + (3 * value * value) / (Math.PI * Math.PI));
}

function expected(muSelf: number, muOther: number, phiOther: number): number {
  return 1 / (1 + Math.exp(-g(phiOther) * (muSelf - muOther)));
}

/** Период без игр: рейтинг стоит, неопределённость растёт. */
export function rateUnplayed(player: Rating): Rating {
  const star = Math.sqrt(phi(player) ** 2 + player.volatility ** 2);
  return { ...player, rd: Math.min(star * SCALE, DEFAULT_RD) };
}

/** Итог одного рейтингового периода: соперник и результат (1 — победа). */
export interface GameResult {
  opponent: Rating;
  score: number;
}

export function rate(player: Rating, results: GameResult[], tau = DEFAULT_TAU): Rating {
  if (results.length === 0) return rateUnplayed(player);

  const muSelf = mu(player);
  const phiSelf = phi(player);

  let varianceInv = 0;
  let deltaSum = 0;
  for (const result of results) {
    const phiOther = phi(result.opponent);
    const gj = g(phiOther);
    const ej = expected(muSelf, mu(result.opponent), phiOther);
    varianceInv += gj * gj * ej * (1 - ej);
    deltaSum += gj * (result.score - ej);
  }
  if (varianceInv === 0) return rateUnplayed(player);

  const v = 1 / varianceInv;
  const delta = v * deltaSum;
  const volatility = newVolatility(phiSelf, v, delta, player.volatility, tau);
  const star = Math.sqrt(phiSelf ** 2 + volatility ** 2);
  const newPhi = 1 / Math.sqrt(1 / (star * star) + 1 / v);

  return {
    rating: (muSelf + newPhi * newPhi * deltaSum) * SCALE + DEFAULT_RATING,
    rd: newPhi * SCALE,
    volatility,
  };
}

/** Шаг 5 статьи Гликмана: итерация Illinois по волатильности. */
function newVolatility(
  phiSelf: number,
  v: number,
  delta: number,
  volatility: number,
  tau: number,
): number {
  const a = Math.log(volatility * volatility);
  const tauSq = tau * tau;
  const phiSq = phiSelf * phiSelf;
  const deltaSq = delta * delta;

  const f = (x: number) => {
    const ex = Math.exp(x);
    const denom = phiSq + v + ex;
    return (ex * (deltaSq - denom)) / (2 * denom * denom) - (x - a) / tauSq;
  };

  let big_a = a;
  let big_b: number;
  if (deltaSq > phiSq + v) {
    big_b = Math.log(deltaSq - phiSq - v);
  } else {
    let k = 1;
    while (f(a - k * tau) < 0) {
      k += 1;
      if (k > 100) return volatility; // недостижимо на настоящих данных
    }
    big_b = a - k * tau;
  }

  let fa = f(big_a);
  let fb = f(big_b);
  for (let i = 0; i < 100 && Math.abs(big_b - big_a) > CONVERGENCE_EPSILON; i += 1) {
    const c = big_a + ((big_a - big_b) * fa) / (fb - fa);
    const fc = f(c);
    if (fc * fb <= 0) {
      big_a = big_b;
      fa = fb;
    } else {
      fa /= 2;
    }
    big_b = c;
    fb = fc;
  }
  return Math.exp(big_a / 2);
}

/**
 * Вероятность победы в одной карте.
 *
 * `temperature` — калибровка уверенности: рейтинг переоценивает разрыв, и логит
 * прогноза сжимается. Значение приходит из снапшота, подобранное по истории.
 */
export function winProbability(player: Rating, opponent: Rating, temperature = 1): number {
  const combined = Math.sqrt(phi(player) ** 2 + phi(opponent) ** 2);
  return 1 / (1 + Math.exp(-temperature * g(combined) * (mu(player) - mu(opponent))));
}

/** Вероятность выиграть серию при независимых картах. */
export function seriesWinProbability(
  player: Rating,
  opponent: Rating,
  bestOf: number,
  temperature = 1,
): number {
  const p = winProbability(player, opponent, temperature);
  const needed = Math.floor(bestOf / 2) + 1;
  let total = 0;
  for (let losses = 0; losses < needed; losses += 1) {
    total += combinations(needed + losses - 1, losses) * p ** needed * (1 - p) ** losses;
  }
  return total;
}

function combinations(n: number, k: number): number {
  let result = 1;
  for (let i = 0; i < k; i += 1) result = (result * (n - i)) / (i + 1);
  return Math.round(result);
}

export interface RatingHistory {
  ratings: Map<number, Rating>;
  /** Сколько карт команды вошло в основу: без этого рейтинг нечем взвесить. */
  played: Map<number, number>;
  periods: number;
}

/**
 * Пересчёт по всей истории вперёд по времени.
 *
 * Повторяет `RatingCalculator.compute`: матчи разложены по рейтинговым периодам,
 * внутри периода все считаются одновременными (оцениваются по снимку на начало
 * периода), а неигравшие команды всё равно получают обновление — их
 * неопределённость растёт от простоя.
 */
export function computeRatings(matches: MapResult[], periodDays = 7): RatingHistory {
  const ordered = [...matches].sort((a, b) => a.ts - b.ts);
  if (ordered.length === 0) return { ratings: new Map(), played: new Map(), periods: 0 };

  const period = periodDays * 86400;
  const origin = ordered[0].ts;
  const buckets = new Map<number, MapResult[]>();
  for (const match of ordered) {
    const start = origin + Math.floor((match.ts - origin) / period) * period;
    const bucket = buckets.get(start);
    if (bucket) bucket.push(match);
    else buckets.set(start, [match]);
  }

  const ratings = new Map<number, Rating>();
  const played = new Map<number, number>();
  const known = new Set<number>();

  for (const start of [...buckets.keys()].sort((a, b) => a - b)) {
    const chunk = buckets.get(start)!;
    const frozen = new Map<number, Rating>();
    for (const team of known) frozen.set(team, ratings.get(team) ?? INITIAL);

    const results = new Map<number, GameResult[]>();
    for (const match of chunk) {
      for (const team of [match.radiant, match.dire]) {
        if (!frozen.has(team)) {
          frozen.set(team, ratings.get(team) ?? INITIAL);
          known.add(team);
        }
        if (!results.has(team)) results.set(team, []);
      }
      const winner = match.radiantWin ? match.radiant : match.dire;
      const loser = match.radiantWin ? match.dire : match.radiant;
      results.get(winner)!.push({ opponent: frozen.get(loser)!, score: 1 });
      results.get(loser)!.push({ opponent: frozen.get(winner)!, score: 0 });
      played.set(winner, (played.get(winner) ?? 0) + 1);
      played.set(loser, (played.get(loser) ?? 0) + 1);
    }

    for (const team of known) {
      ratings.set(team, rate(frozen.get(team) ?? INITIAL, results.get(team) ?? []));
    }
  }

  return { ratings, played, periods: buckets.size };
}
