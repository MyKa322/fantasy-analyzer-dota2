// Симуляция сетки плей-офф в браузере — порт `BracketSimulator` из
// `backend/app/analytics/simulate.py`.
//
// Нужна там же, где и рейтинг: пользователь меняет основу оценки, и вслед за
// рейтингом должен меняться прогноз. Структуру сетки этот модуль не знает — она
// приходит из снапшота, посчитанная бэкендом. Так копия остаётся одна: здесь
// только розыгрыш, а «кто куда попадает» описано в одном месте на весь проект.

import { seriesWinProbability, type Rating } from "./rating";

export interface BracketSource {
  slot: string;
  winner: boolean;
}

export interface BracketSlot {
  key: string;
  round: string;
  side: string;
  sources: BracketSource[];
  elimination_place: string | null;
}

export interface BracketOdds {
  /** team_id -> вероятность. */
  champion: Map<number, number>;
  final: Map<number, number>;
  top4: Map<number, number>;
  /** Ключ места -> team_id -> вероятность выиграть его. */
  win: Map<string, Map<number, number>>;
  runs: number;
}

export interface BracketInput {
  structure: BracketSlot[];
  /** Пары четвертьфиналов в порядке ubqf1..ubqf4. */
  quarterfinals: [number, number][];
  ratings: Map<number, Rating>;
  bestOf: number;
  grandFinalBestOf: number;
  temperature: number;
  /** Уже сыгранное: ключ места -> id победителя. */
  results?: Map<string, number>;
  /** Уже известные участники места: ключ -> пара id. */
  participants?: Map<string, [number, number]>;
  runs?: number;
  seed?: number;
}

/** Генератор с зерном: тот же выбор основы должен давать те же числа. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const placeValue = (place: string) => Number.parseInt(place.split("-")[0], 10);

export function simulateBracket(input: BracketInput): BracketOdds {
  const {
    structure,
    quarterfinals,
    ratings,
    bestOf,
    grandFinalBestOf,
    temperature,
    results = new Map<string, number>(),
    participants = new Map<string, [number, number]>(),
    runs = 20000,
    seed = 2,
  } = input;

  const qfKeys = structure.filter((slot) => slot.sources.length === 0).map((slot) => slot.key);
  const teams = [...new Set(quarterfinals.flat())];

  // Матрица вероятностей считается один раз: пар всего восемь на восемь, а
  // прогонов двадцать тысяч.
  const probability = new Map<string, number>();
  const pairKey = (a: number, b: number, grand: boolean) => `${a}:${b}:${grand ? 5 : 3}`;
  for (const a of teams) {
    for (const b of teams) {
      if (a === b) continue;
      const left = ratings.get(a);
      const right = ratings.get(b);
      for (const grand of [false, true]) {
        const value =
          left && right
            ? seriesWinProbability(left, right, grand ? grandFinalBestOf : bestOf, temperature)
            : 0.5;
        probability.set(pairKey(a, b, grand), value);
      }
    }
  }

  const champion = new Map<number, number>();
  const final = new Map<number, number>();
  const top4 = new Map<number, number>();
  const win = new Map<string, Map<number, number>>(structure.map((slot) => [slot.key, new Map()]));
  const bump = (counter: Map<number, number>, team: number) =>
    counter.set(team, (counter.get(team) ?? 0) + 1);

  const random = mulberry32(seed);
  for (let run = 0; run < runs; run += 1) {
    const winners = new Map<string, number>();
    const pairs = new Map<string, [number, number]>();
    const places = new Map<number, string>();

    const resolve = (source: BracketSource): number => {
      const slotWinner = winners.get(source.slot)!;
      if (source.winner) return slotWinner;
      const [left, right] = pairs.get(source.slot)!;
      return slotWinner === left ? right : left;
    };

    for (const slot of structure) {
      const known = participants.get(slot.key);
      let pair: [number, number];
      if (known) {
        pair = known;
      } else if (slot.sources.length === 0) {
        pair = quarterfinals[qfKeys.indexOf(slot.key)];
      } else {
        pair = [resolve(slot.sources[0]), resolve(slot.sources[1])];
      }
      pairs.set(slot.key, pair);

      const fixed = results.get(slot.key);
      const [a, b] = pair;
      const winner =
        fixed ??
        (random() < (probability.get(pairKey(a, b, slot.key === "gf")) ?? 0.5) ? a : b);
      winners.set(slot.key, winner);

      if (slot.elimination_place) {
        places.set(winner === a ? b : a, slot.elimination_place);
      }
      bump(win.get(slot.key)!, winner);
    }

    const grandFinal = pairs.get("gf");
    const titleist = winners.get("gf");
    if (grandFinal && titleist != null) {
      places.set(titleist, "1");
      places.set(grandFinal[0] === titleist ? grandFinal[1] : grandFinal[0], "2");
      bump(champion, titleist);
      bump(final, grandFinal[0]);
      bump(final, grandFinal[1]);
    }
    for (const [team, place] of places) {
      if (placeValue(place) <= 4) bump(top4, team);
    }
  }

  const share = (counter: Map<number, number>) =>
    new Map([...counter].map(([team, count]) => [team, count / runs]));

  return {
    champion: share(champion),
    final: share(final),
    top4: share(top4),
    win: new Map([...win].map(([key, counter]) => [key, share(counter)])),
    runs,
  };
}

/** Ключи мест, которые сетка знает как объявленные четвертьфиналы. */
export function quarterfinalKeys(structure: BracketSlot[]): string[] {
  return structure.filter((slot) => slot.sources.length === 0).map((slot) => slot.key);
}
