// Общие подписи: то, что встречается на нескольких вкладках сразу, плюс
// словари, которыми переводятся строки из снапшота (условия титулов, описания
// трейтов, названия статов).
//
// Формат: один ключ — все языки рядом. Так видно пропуск при чтении, а не
// только при сборке, и перевод правится там же, где оригинал.

import type { Locale } from "../site";

export type Message = Record<Locale, string>;

export const common = {
  // --- кнопки и состояния ---------------------------------------------------
  "common.loading": {
    ru: "Загружаю…",
    en: "Loading…",
    uk: "Завантажую…",
    zh: "加载中…",
  },
  "common.calculating": {
    ru: "Считаю…",
    en: "Calculating…",
    uk: "Рахую…",
    zh: "计算中…",
  },
  "common.back": {
    ru: "← К списку",
    en: "← Back to list",
    uk: "← До списку",
    zh: "← 返回列表",
  },
  "common.remove": { ru: "Убрать", en: "Remove", uk: "Прибрати", zh: "移除" },
  "common.noData": {
    ru: "Данных нет.",
    en: "No data.",
    uk: "Даних немає.",
    zh: "暂无数据。",
  },
  "common.dash": { ru: "—", en: "—", uk: "—", zh: "—" },

  // --- заголовки колонок и полей --------------------------------------------
  "common.team": { ru: "Команда", en: "Team", uk: "Команда", zh: "战队" },
  "common.teams": { ru: "Команды", en: "Teams", uk: "Команди", zh: "战队" },
  "common.player": { ru: "Игрок", en: "Player", uk: "Гравець", zh: "选手" },
  "common.players": { ru: "Игроки", en: "Players", uk: "Гравці", zh: "选手" },
  "common.role": { ru: "Роль", en: "Role", uk: "Роль", zh: "位置" },
  "common.stat": { ru: "Стат", en: "Stat", uk: "Стат", zh: "数据项" },
  "common.quality": { ru: "Качество", en: "Quality", uk: "Якість", zh: "品质" },
  "common.trait": { ru: "Трейт", en: "Trait", uk: "Трейт", zh: "特性" },
  "common.matches": { ru: "Матчи", en: "Matches", uk: "Матчі", zh: "比赛" },
  "common.perMap": { ru: "За карту", en: "Per map", uk: "За карту", zh: "场均" },
  "common.perPeriod": {
    ru: "За период",
    en: "Per period",
    uk: "За період",
    zh: "赛段总计",
  },
  "common.ceiling": { ru: "Потолок", en: "Ceiling", uk: "Стеля", zh: "上限" },
  "common.points": { ru: "Очков", en: "Points", uk: "Очок", zh: "积分" },
  "common.mapsShort": { ru: "Карт", en: "Maps", uk: "Карт", zh: "场次" },
  "common.median": { ru: "Медиана", en: "Median", uk: "Медіана", zh: "中位数" },
  "common.form": { ru: "Форма", en: "Form", uk: "Форма", zh: "近期状态" },
  "common.average": { ru: "среднее", en: "average", uk: "середнє", zh: "平均" },
  "common.expectation": {
    ru: "Ожидание",
    en: "Expected",
    uk: "Очікування",
    zh: "期望值",
  },
  "common.wins": { ru: "Победы", en: "Wins", uk: "Перемоги", zh: "胜负" },
  "common.rating": { ru: "Рейтинг", en: "Rating", uk: "Рейтинг", zh: "评分" },
  "common.kda": { ru: "К/С/А", en: "K/D/A", uk: "В/С/А", zh: "K/D/A" },
  "common.mapsWithStat": {
    ru: "Карт со статом",
    en: "Maps with stat",
    uk: "Карт зі статом",
    zh: "触发场次",
  },
  "common.mapsWithStatHint": {
    ru: "Доля карт, где стат вообще был",
    en: "Share of maps where the stat happened at all",
    uk: "Частка карт, де стат узагалі був",
    zh: "该数据项实际出现的场次占比",
  },
  "common.formHint": {
    ru: "Последние 30 дней к предыдущим 60",
    en: "Last 30 days against the previous 60",
    uk: "Останні 30 днів до попередніх 60",
    zh: "最近 30 天与此前 60 天的对比",
  },
  "common.formNoSample": {
    ru: "карт для сравнения мало",
    en: "too few maps to compare",
    uk: "карт для порівняння замало",
    zh: "场次太少，无法对比",
  },
  "common.topTwoMaps": {
    ru: "топ-2 карты лучшей серии",
    en: "top 2 maps of the best series",
    uk: "топ-2 карти найкращої серії",
    zh: "最佳系列赛中的前 2 场",
  },

  // --- склонения ------------------------------------------------------------
  // Форма выбирается через Intl.PluralRules: в русском и украинском их четыре,
  // в английском две, в китайском одна. Ключи одинаковые у всех языков — иначе
  // проверка полноты словаря пропустит пропущенный перевод.
  "plural.maps.one": { ru: "{n} карта", en: "{n} map", uk: "{n} карта", zh: "{n} 场" },
  "plural.maps.few": { ru: "{n} карты", en: "{n} maps", uk: "{n} карти", zh: "{n} 场" },
  "plural.maps.many": { ru: "{n} карт", en: "{n} maps", uk: "{n} карт", zh: "{n} 场" },
  "plural.maps.other": { ru: "{n} карт", en: "{n} maps", uk: "{n} карт", zh: "{n} 场" },
  "plural.options.one": {
    ru: "{n} вариант",
    en: "{n} option",
    uk: "{n} варіант",
    zh: "{n} 种搭配",
  },
  "plural.options.few": {
    ru: "{n} варианта",
    en: "{n} options",
    uk: "{n} варіанти",
    zh: "{n} 种搭配",
  },
  "plural.options.many": {
    ru: "{n} вариантов",
    en: "{n} options",
    uk: "{n} варіантів",
    zh: "{n} 种搭配",
  },
  "plural.options.other": {
    ru: "{n} вариантов",
    en: "{n} options",
    uk: "{n} варіантів",
    zh: "{n} 种搭配",
  },
  "plural.tournaments.one": {
    ru: "{n} разыгранный турнир",
    en: "{n} tournament played out",
    uk: "{n} розіграний турнір",
    zh: "已模拟 {n} 次赛事",
  },
  "plural.tournaments.few": {
    ru: "{n} разыгранных турнира",
    en: "{n} tournaments played out",
    uk: "{n} розіграних турніри",
    zh: "已模拟 {n} 次赛事",
  },
  "plural.tournaments.many": {
    ru: "{n} разыгранных турниров",
    en: "{n} tournaments played out",
    uk: "{n} розіграних турнірів",
    zh: "已模拟 {n} 次赛事",
  },
  "plural.tournaments.other": {
    ru: "{n} разыгранных турниров",
    en: "{n} tournaments played out",
    uk: "{n} розіграних турнірів",
    zh: "已模拟 {n} 次赛事",
  },
  "common.minutes": { ru: "{n} мин", en: "{n} min", uk: "{n} хв", zh: "{n} 分钟" },

  // --- роли -----------------------------------------------------------------
  "role.core": { ru: "Core Duo", en: "Core Duo", uk: "Core Duo", zh: "核心双人组" },
  "role.mid": { ru: "Mid", en: "Mid", uk: "Mid", zh: "中单" },
  "role.support": {
    ru: "Support Duo",
    en: "Support Duo",
    uk: "Support Duo",
    zh: "辅助双人组",
  },
  "role.unknown": {
    ru: "роль не размечена",
    en: "role not assigned",
    uk: "роль не розмічена",
    zh: "位置未标注",
  },
  "role.all": { ru: "Все роли", en: "All roles", uk: "Усі ролі", zh: "全部位置" },

  // --- цвета слотов ---------------------------------------------------------
  "color.red": {
    ru: "Красные — Core и Mid",
    en: "Red — Core and Mid",
    uk: "Червоні — Core і Mid",
    zh: "红色 — 核心与中单",
  },
  "color.blue": {
    ru: "Синие — Mid и Support",
    en: "Blue — Mid and Support",
    uk: "Сині — Mid і Support",
    zh: "蓝色 — 中单与辅助",
  },
  "color.green": {
    ru: "Зелёные — любая роль",
    en: "Green — any role",
    uk: "Зелені — будь-яка роль",
    zh: "绿色 — 任意位置",
  },

  // --- трейты: описание из правил компендиума -------------------------------
  "trait.none": {
    ru: "без трейта",
    en: "no trait",
    uk: "без трейта",
    zh: "无特性",
  },
  "trait.noneOption": {
    ru: "Без трейта",
    en: "No trait",
    uk: "Без трейта",
    zh: "无特性",
  },
  "trait.fractal.description": {
    ru: "+60%, если все качества эмблем на баннере разные",
    en: "+60% if every emblem on the banner has a different quality",
    uk: "+60%, якщо всі якості емблем на банері різні",
    zh: "若战旗上所有纹章品质各不相同，+60%",
  },
  "trait.benevolent.description": {
    ru: "+20% соседним эмблемам",
    en: "+20% to adjacent emblems",
    uk: "+20% сусіднім емблемам",
    zh: "相邻纹章 +20%",
  },
  "trait.vampiric.description": {
    ru: "+50% себе, -10% соседним эмблемам",
    en: "+50% to itself, −10% to adjacent emblems",
    uk: "+50% собі, −10% сусіднім емблемам",
    zh: "自身 +50%，相邻纹章 −10%",
  },
  "trait.unique.description": {
    ru: "+30%, если это единственная Unique эмблема на баннере",
    en: "+30% if it is the only Unique emblem on the banner",
    uk: "+30%, якщо це єдина Unique емблема на банері",
    zh: "若为战旗上唯一的 Unique 纹章，+30%",
  },
  "trait.friendly.description": {
    ru: "+50%, если на баннере минимум 3 Friendly эмблемы",
    en: "+50% if the banner holds at least 3 Friendly emblems",
    uk: "+50%, якщо на банері щонайменше 3 Friendly емблеми",
    zh: "若战旗上至少有 3 个 Friendly 纹章，+50%",
  },

  // --- условия Coaching Titles ----------------------------------------------
  "title.crimson.condition": {
    ru: "герой красного цвета",
    en: "a red hero",
    uk: "герой червоного кольору",
    zh: "红色系英雄",
  },
  "title.cerulean.condition": {
    ru: "герой синего цвета",
    en: "a blue hero",
    uk: "герой синього кольору",
    zh: "蓝色系英雄",
  },
  "title.emerald.condition": {
    ru: "герой зелёного цвета",
    en: "a green hero",
    uk: "герой зеленого кольору",
    zh: "绿色系英雄",
  },
  "title.royal.condition": {
    ru: "герой фиолетового цвета",
    en: "a purple hero",
    uk: "герой фіолетового кольору",
    zh: "紫色系英雄",
  },
  "title.golden.condition": {
    ru: "жёлтый или коричневый герой",
    en: "a yellow or brown hero",
    uk: "жовтий або коричневий герой",
    zh: "黄色或棕色系英雄",
  },
  "title.elemental.condition": {
    ru: "водный, огненный или ледяной герой",
    en: "a water, fire or ice hero",
    uk: "водяний, вогняний або крижаний герой",
    zh: "水、火或冰属性英雄",
  },
  "title.otherworldly.condition": {
    ru: "нежить, демон или дух",
    en: "an undead, demon or spirit",
    uk: "нежить, демон або дух",
    zh: "亡灵、恶魔或灵体",
  },
  "title.heroic.condition": {
    ru: "герой в плаще или маске",
    en: "a hero in a cape or mask",
    uk: "герой у плащі або масці",
    zh: "披斗篷或戴面具的英雄",
  },
  "title.tormented.condition": {
    ru: "любой игрок погиб от Торментора",
    en: "any player died to the Tormentor",
    uk: "будь-який гравець загинув від Торментора",
    zh: "任意选手被折磨者击杀",
  },
  "title.flayed.condition": {
    ru: "первая кровь до стартового гонга",
    en: "first blood before the horn",
    uk: "перша кров до стартового гонга",
    zh: "开局锣声前拿到一血",
  },
  "title.patient.condition": {
    ru: "первая кровь позже 10-й минуты",
    en: "first blood after the 10th minute",
    uk: "перша кров пізніше 10-ї хвилини",
    zh: "一血发生在第 10 分钟之后",
  },
  "title.underdog.condition": {
    ru: "игра проиграна",
    en: "the game is lost",
    uk: "гра програна",
    zh: "该场比赛落败",
  },
  "title.decisive.condition": {
    ru: "игра короче 25 минут",
    en: "the game is shorter than 25 minutes",
    uk: "гра коротша за 25 хвилин",
    zh: "比赛时长短于 25 分钟",
  },
  "title.clutch.condition": {
    ru: "последняя возможная карта серии",
    en: "the last possible map of the series",
    uk: "остання можлива карта серії",
    zh: "系列赛的决胜局",
  },
  "title.lucky.condition": {
    ru: "время матча заканчивается на 8",
    en: "the match duration ends in an 8",
    uk: "час матчу закінчується на 8",
    zh: "比赛时长的末位数字是 8",
  },
  "title.cruel.condition": {
    ru: "игрок убит в своём фонтане",
    en: "the player is killed in their own fountain",
    uk: "гравця вбито у своєму фонтані",
    zh: "选手在己方泉水被击杀",
  },

  // --- пояснения к оценке титулов -------------------------------------------
  // Числа подставляются: {pct} — доля карт, {hits}/{total} — сама выборка.
  "title.note.heroShare": {
    ru: "{pct}% выборов — герои из списка ({hits} из {total})",
    en: "{pct}% of picks are heroes from the list ({hits} of {total})",
    uk: "{pct}% виборів — герої зі списку ({hits} з {total})",
    zh: "{pct}% 的英雄选择来自该称号的列表（{total} 次中的 {hits} 次）",
  },
  "title.note.short": {
    ru: "{pct}% игр короче 25 минут",
    en: "{pct}% of games are shorter than 25 minutes",
    uk: "{pct}% ігор коротші за 25 хвилин",
    zh: "{pct}% 的比赛短于 25 分钟",
  },
  "title.note.lucky": {
    ru: "{pct}% игр закончились на цифру 8",
    en: "{pct}% of games ended on the digit 8",
    uk: "{pct}% ігор закінчилися на цифру 8",
    zh: "{pct}% 的比赛时长以数字 8 结尾",
  },
  "title.note.lost": {
    ru: "{pct}% игр проиграно",
    en: "{pct}% of games are losses",
    uk: "{pct}% ігор програно",
    zh: "{pct}% 的比赛为失利",
  },
  "title.note.patient": {
    ru: "{pct}% игр без первой крови до 10:00 (по {sample} картам из {total})",
    en: "{pct}% of games with no first blood before 10:00 (over {sample} maps of {total})",
    uk: "{pct}% ігор без першої крові до 10:00 (за {sample} картами з {total})",
    zh: "{pct}% 的比赛在 10:00 前没有一血（统计了 {total} 场中的 {sample} 场）",
  },
  "title.note.decider": {
    ru: "{pct}% карт были последними возможными в серии",
    en: "{pct}% of maps were the last possible one of their series",
    uk: "{pct}% карт були останніми можливими в серії",
    zh: "{pct}% 的比赛是所在系列赛的决胜局",
  },
  "title.note.tormented": {
    ru: "OpenDota не различает, кто нанёс смертельный удар Торментором",
    en: "OpenDota does not record who landed the killing blow with the Tormentor",
    uk: "OpenDota не розрізняє, хто завдав смертельного удару Торментором",
    zh: "OpenDota 不记录折磨者的击杀由谁造成",
  },
  "title.note.flayed": {
    ru: "время первой крови OpenDota отдаёт нулём и когда события не поймала — кровь до гонга от пропуска не отличить",
    en: "OpenDota reports a first blood time of zero both before the horn and when it missed the event — the two cannot be told apart",
    uk: "час першої крові OpenDota віддає нулем і коли події не спіймала — кров до гонга від пропуску не відрізнити",
    zh: "OpenDota 在开局前一血和未捕捉到事件这两种情况下都返回 0，两者无法区分",
  },
  "title.note.cruel": {
    ru: "убийства у фонтана в данных не помечены",
    en: "fountain kills are not flagged in the data",
    uk: "вбивства біля фонтана в даних не позначені",
    zh: "数据中没有标记泉水击杀",
  },
  "title.note.noHeroes": {
    ru: "нет справочника героев — выполните `cli.py ingest-heroes`",
    en: "no hero reference — run `cli.py ingest-heroes`",
    uk: "немає довідника героїв — виконайте `cli.py ingest-heroes`",
    zh: "缺少英雄对照表——请运行 `cli.py ingest-heroes`",
  },
  "title.note.outside": {
    ru: "условие вне наших данных",
    en: "the condition is outside our data",
    uk: "умова поза нашими даними",
    zh: "该条件不在我们的数据范围内",
  },
  "title.note.notEnough": {
    ru: "недостаточно данных",
    en: "not enough data",
    uk: "недостатньо даних",
    zh: "数据不足",
  },

  // --- ошибки ---------------------------------------------------------------
  "error.snapshot": {
    ru: "не удалось загрузить снапшот: {status}",
    en: "failed to load the snapshot: {status}",
    uk: "не вдалося завантажити знімок: {status}",
    zh: "加载数据快照失败：{status}",
  },
  "error.profiles": {
    ru: "не удалось загрузить профили: {status}",
    en: "failed to load the profiles: {status}",
    uk: "не вдалося завантажити профілі: {status}",
    zh: "加载主页数据失败：{status}",
  },
  "error.offline": {
    ru: "Эта операция требует локального бэкенда — на опубликованной странице данные берутся из снапшота, который обновляется по расписанию.",
    en: "This action needs the local backend — the published page reads a snapshot that is refreshed on a schedule.",
    uk: "Ця операція потребує локального бекенда — на опублікованій сторінці дані беруться зі знімка, який оновлюється за розкладом.",
    zh: "该操作需要本地后端——已发布的页面读取的是按计划更新的数据快照。",
  },
  "error.gap": {
    ru: "{color}: нужно {need}, есть {have}",
    en: "{color}: {need} needed, {have} available",
    uk: "{color}: потрібно {need}, є {have}",
    zh: "{color}：需要 {need} 个，现有 {have} 个",
  },
} satisfies Record<string, Message>;
