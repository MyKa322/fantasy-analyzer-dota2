// Языки сайта и то, что о нём должен знать поисковик.
//
// Файл намеренно без React и без импортов: его читает не только приложение, но
// и сборка (vite.config.ts), которая из этих же строк делает <title>, описание,
// hreflang и вводный блок для краулера. Держать тексты в двух местах — верный
// способ получить страницу, где заголовок вкладки на одном языке, а описание в
// выдаче на другом.

export const LOCALES = [
  "en",
  "ru",
  "uk",
  "zh",
  "es",
  "pt",
  "de",
  "fr",
  "pl",
  "tr",
  "id",
  "vi",
] as const;

export type Locale = (typeof LOCALES)[number];

/**
 * Язык по умолчанию: он лежит в корне сайта и он же x-default для поисковика.
 *
 * Английский, а не русский, хотя писалось всё по-русски: страницу ищут по
 * запросам про The International, а их набирают латиницей со всего мира.
 * Русская версия никуда не делась — она переехала в /ru/.
 */
export const DEFAULT_LOCALE: Locale = "en";

/** Подпись в переключателе — всегда на своём языке, а не в переводе. */
export const LOCALE_NAME: Record<Locale, string> = {
  en: "English",
  ru: "Русский",
  uk: "Українська",
  zh: "中文",
  es: "Español",
  pt: "Português",
  de: "Deutsch",
  fr: "Français",
  pl: "Polski",
  tr: "Türkçe",
  id: "Bahasa Indonesia",
  vi: "Tiếng Việt",
};

/** Значение атрибута lang и тега hreflang. */
export const HTML_LANG: Record<Locale, string> = {
  en: "en",
  ru: "ru",
  uk: "uk",
  zh: "zh-Hans",
  es: "es",
  // Португальский переведён в бразильской норме — там и аудитория Dota.
  pt: "pt-BR",
  de: "de",
  fr: "fr",
  pl: "pl",
  tr: "tr",
  id: "id",
  vi: "vi",
};

/** Форма локали для Intl: разделитель другой, чем в HTML. */
export const INTL_LOCALE: Record<Locale, string> = {
  en: "en-US",
  ru: "ru-RU",
  uk: "uk-UA",
  zh: "zh-CN",
  es: "es-ES",
  pt: "pt-BR",
  de: "de-DE",
  fr: "fr-FR",
  pl: "pl-PL",
  tr: "tr-TR",
  id: "id-ID",
  vi: "vi-VN",
};

/** og:locale — у Open Graph свой формат, с подчёркиванием. */
export const OG_LOCALE: Record<Locale, string> = {
  en: "en_US",
  ru: "ru_RU",
  uk: "uk_UA",
  zh: "zh_CN",
  es: "es_ES",
  pt: "pt_BR",
  de: "de_DE",
  fr: "fr_FR",
  pl: "pl_PL",
  tr: "tr_TR",
  id: "id_ID",
  vi: "vi_VN",
};

/** Канонический адрес опубликованной страницы. */
export const SITE_URL = "https://myka322.github.io/fantasy-analyzer-dota2";

/** Адрес языковой версии: английская лежит в корне, остальные — в подкаталогах. */
export function localeUrl(locale: Locale, base = `${SITE_URL}/`): string {
  return locale === DEFAULT_LOCALE ? base : `${base}${locale}/`;
}

export interface SiteMeta {
  /** <title> и og:title. До 60 символов — иначе выдача обрежет. */
  title: string;
  /** meta description и og:description. 140–160 символов. */
  description: string;
  /** Заголовок вводного блока — того, что видно до загрузки приложения. */
  headline: string;
  /** Два-три предложения о том, что здесь считают. */
  intro: string;
  /** Что умеет страница — списком. */
  features: string[];
  teamsHeading: string;
  /** Подпись под списком команд. */
  teamsNote: string;
  /** Строка «загружаю» для тех, у кого приложение ещё не отрисовалось. */
  loading: string;
}

/**
 * Тексты для поисковика и для первого экрана.
 *
 * Это не дубль интерфейса: краулеру нужен связный текст про то, что за
 * страница, а интерфейс состоит из подписей к таблицам. Поэтому описание
 * написано отдельно и словами, которые люди набирают в поиске.
 */
export const SITE: Record<Locale, SiteMeta> = {
  en: {
    title: "Compendium Analyzer — TI15 Fantasy and Predictions",
    description:
      "The International 2026 compendium analytics: War Banner emblem picks per role, Fantasy Draft point projections, Swiss bracket probabilities, Glicko-2 ratings and full team, player and match pages built from OpenDota data.",
    headline: "The International 2026 compendium analytics",
    intro:
      "Two things decide most of the points a compendium loses: which emblems go on each role's War Banner, and how the group stage predictions are laid out. Both are computed from the attending teams' real OpenDota matches, not from the glossary price list.",
    features: [
      "War Banner emblem picks for Core Duo, Mid and Support Duo — every combination checked, traits included",
      "Your own emblem inventory: which of the sixteen teams turns your rolls into the most points",
      "Fantasy Draft point projection for the period, with ceiling, floor and per-map spread",
      "Swiss bucket probabilities and a ready prediction layout optimised for expected points",
      "Coaching Titles ranked by what they actually pay out, not by the percentage printed on them",
      "Team, player and match pages: OpenDota statistics, hero pool, Glicko-2 rating and our own analysis",
    ],
    teamsHeading: "The International 2026 teams",
    teamsNote:
      "Every team has a page with its matches, per-map averages, hero pool and a role-by-role breakdown.",
    loading: "Loading data…",
  },
  ru: {
    title: "Compendium Analyzer — Fantasy и Predictions для The International 2026",
    description:
      "Аналитика компендиума TI15: подбор War Banner и эмблем по ролям, прогноз очков Fantasy Draft, вероятности корзин Swiss, рейтинги Glicko-2, страницы всех команд, игроков и матчей по данным OpenDota.",
    headline: "Аналитика компендиума The International 2026",
    intro:
      "Считает две вещи, на которых в компендиуме теряют больше всего очков: какие эмблемы поставить на War Banner каждой роли и как расставить предсказания группового этапа. Обе задачи решаются по реальным матчам участников из OpenDota, а не по ценам из глоссария.",
    features: [
      "Подбор эмблем War Banner для Core Duo, Mid и Support Duo — перебором всех комбинаций с учётом трейтов",
      "Свой инвентарь эмблем: кому из шестнадцати команд выпавшие роллы принесут больше всего очков",
      "Прогноз очков Fantasy Draft за период — с потолком, полом и разбросом по картам",
      "Вероятности корзин Swiss и готовая расстановка предсказаний под максимум очков",
      "Coaching Titles: сколько реально даст титул, а не сколько написано в описании",
      "Страницы команд, игроков и матчей: статистика OpenDota, пул героев, рейтинг Glicko-2 и наш анализ",
    ],
    teamsHeading: "Участники The International 2026",
    teamsNote:
      "У каждой команды есть страница с матчами, средними за карту, пулом героев и разбором по ролям.",
    loading: "Загружаю данные…",
  },
  uk: {
    title: "Compendium Analyzer — Fantasy і Predictions для The International 2026",
    description:
      "Аналітика компендіума TI15: добір емблем War Banner за ролями, прогноз очок Fantasy Draft, імовірності кошиків Swiss, рейтинги Glicko-2 та сторінки всіх команд, гравців і матчів за даними OpenDota.",
    headline: "Аналітика компендіума The International 2026",
    intro:
      "Рахує дві речі, на яких у компендіумі втрачають найбільше очок: які емблеми поставити на War Banner кожної ролі та як розставити передбачення групового етапу. Обидві задачі розв'язуються за реальними матчами учасників з OpenDota, а не за цінами з глосарія.",
    features: [
      "Добір емблем War Banner для Core Duo, Mid і Support Duo — перебором усіх комбінацій із урахуванням трейтів",
      "Власний інвентар емблем: кому з шістнадцяти команд ваші роли принесуть найбільше очок",
      "Прогноз очок Fantasy Draft за період — зі стелею, підлогою та розкидом по картах",
      "Імовірності кошиків Swiss і готова розстановка передбачень під максимум очок",
      "Coaching Titles: скільки титул дасть насправді, а не скільки написано в описі",
      "Сторінки команд, гравців і матчів: статистика OpenDota, пул героїв, рейтинг Glicko-2 та наш аналіз",
    ],
    teamsHeading: "Учасники The International 2026",
    teamsNote:
      "У кожної команди є сторінка з матчами, середніми за карту, пулом героїв і розбором за ролями.",
    loading: "Завантажую дані…",
  },
  zh: {
    title: "Compendium Analyzer — TI15 梦幻联赛与赛果预测分析",
    description:
      "TI15 勇士令状数据分析：按位置推荐战旗纹章搭配、梦幻联赛积分预测、瑞士轮分组概率、Glicko-2 战队评分，以及基于 OpenDota 数据的战队、选手与单场比赛页面。",
    headline: "The International 2026 勇士令状数据分析",
    intro:
      "勇士令状里最容易丢分的有两件事：每个位置的战旗该放哪些纹章，以及小组赛的预测该怎么排。这两件事都按参赛队伍在 OpenDota 上的真实比赛来算，而不是照搬说明里的分值。",
    features: [
      "为 Core Duo、Mid 和 Support Duo 推荐战旗纹章——穷举所有组合，并计入特性之间的相互影响",
      "输入自己已有的纹章：这套纹章放在十六支队伍中的哪一对身上得分最高",
      "梦幻联赛赛段积分预测——含上限、下限和逐场波动",
      "瑞士轮各分组概率，以及按期望得分最优排好的预测方案",
      "教练称号按实际能拿到的加成排序，而不是按称号上写的百分比",
      "战队、选手与比赛页面：OpenDota 数据、英雄池、Glicko-2 评分，以及我们自己的分析",
    ],
    teamsHeading: "TI15 参赛队伍",
    teamsNote: "每支队伍都有主页：比赛列表、场均数据、英雄池和分位置的拆解。",
    loading: "正在加载数据…",
  },
  es: {
    title: "Compendium Analyzer — Fantasy y Predictions del TI15",
    description:
      "Analítica del compendio de The International 2026: emblemas del War Banner por rol, proyección de puntos de Fantasy Draft, probabilidades del sistema suizo, ratings Glicko-2 y páginas de equipos, jugadores y partidas con datos de OpenDota.",
    headline: "Analítica del compendio de The International 2026",
    intro:
      "Dos cosas deciden la mayor parte de los puntos que se pierden en el compendio: qué emblemas van en el War Banner de cada rol y cómo se reparten las predicciones de la fase de grupos. Ambas se calculan con las partidas reales de los equipos en OpenDota, no con la lista de precios del glosario.",
    features: [
      "Emblemas del War Banner para Core Duo, Mid y Support Duo: se prueban todas las combinaciones, rasgos incluidos",
      "Tu propio inventario de emblemas: cuál de los dieciséis equipos convierte tus roles en más puntos",
      "Proyección de puntos de Fantasy Draft para el periodo, con techo, suelo y dispersión por mapa",
      "Probabilidades de las casillas del suizo y una disposición de predicciones optimizada para los puntos esperados",
      "Coaching Titles ordenados por lo que realmente pagan, no por el porcentaje impreso en ellos",
      "Páginas de equipos, jugadores y partidas: estadísticas de OpenDota, repertorio de héroes, rating Glicko-2 y nuestro análisis",
    ],
    teamsHeading: "Equipos de The International 2026",
    teamsNote:
      "Cada equipo tiene una página con sus partidas, medias por mapa, repertorio de héroes y desglose rol por rol.",
    loading: "Cargando datos…",
  },
  pt: {
    title: "Compendium Analyzer — Fantasy e Predictions do TI15",
    description:
      "Análise do compêndio do The International 2026: emblemas do War Banner por função, projeção de pontos do Fantasy Draft, probabilidades do sistema suíço, ratings Glicko-2 e páginas de times, jogadores e partidas com dados da OpenDota.",
    headline: "Análise do compêndio do The International 2026",
    intro:
      "Duas coisas decidem a maior parte dos pontos que se perdem no compêndio: quais emblemas vão no War Banner de cada função e como as previsões da fase de grupos são distribuídas. As duas são calculadas a partir das partidas reais dos times na OpenDota, não da tabela de preços do glossário.",
    features: [
      "Emblemas do War Banner para Core Duo, Mid e Support Duo — todas as combinações testadas, traços incluídos",
      "Seu próprio inventário de emblemas: qual dos dezesseis times transforma seus rolls em mais pontos",
      "Projeção de pontos do Fantasy Draft para o período, com teto, piso e dispersão por mapa",
      "Probabilidades das casas do suíço e uma disposição de previsões otimizada para os pontos esperados",
      "Coaching Titles ordenados pelo que realmente rendem, não pela porcentagem escrita neles",
      "Páginas de times, jogadores e partidas: estatísticas da OpenDota, leque de heróis, rating Glicko-2 e nossa análise",
    ],
    teamsHeading: "Times do The International 2026",
    teamsNote:
      "Cada time tem uma página com suas partidas, médias por mapa, leque de heróis e um recorte por função.",
    loading: "Carregando dados…",
  },
  de: {
    title: "Compendium Analyzer — TI15 Fantasy und Predictions",
    description:
      "Kompendium-Analyse zum The International 2026: War-Banner-Embleme je Rolle, Punkteprojektion für den Fantasy Draft, Wahrscheinlichkeiten im Schweizer System, Glicko-2-Ratings sowie Team-, Spieler- und Spielseiten aus OpenDota-Daten.",
    headline: "Kompendium-Analyse zum The International 2026",
    intro:
      "Zwei Dinge entscheiden über die meisten Punkte, die im Kompendium verloren gehen: welche Embleme auf das War Banner jeder Rolle kommen und wie die Tipps der Gruppenphase gelegt werden. Beides wird aus den echten OpenDota-Spielen der Teilnehmer berechnet, nicht aus der Preisliste im Glossar.",
    features: [
      "War-Banner-Embleme für Core Duo, Mid und Support Duo — jede Kombination geprüft, Traits inklusive",
      "Dein eigenes Emblem-Inventar: welches der sechzehn Teams aus deinen Rolls die meisten Punkte macht",
      "Punkteprojektion des Fantasy Draft für den Zeitraum, mit Ober- und Untergrenze und Streuung je Map",
      "Wahrscheinlichkeiten der Felder im Schweizer System und eine fertige, auf Punkterwartung optimierte Tippreihe",
      "Coaching Titles danach sortiert, was sie tatsächlich einbringen, nicht nach dem aufgedruckten Prozentwert",
      "Team-, Spieler- und Spielseiten: OpenDota-Statistik, Heldenpool, Glicko-2-Rating und unsere eigene Analyse",
    ],
    teamsHeading: "Teams beim The International 2026",
    teamsNote:
      "Jedes Team hat eine Seite mit seinen Spielen, Durchschnitten pro Map, Heldenpool und einer Aufschlüsselung nach Rollen.",
    loading: "Daten werden geladen…",
  },
  fr: {
    title: "Compendium Analyzer — Fantasy et Predictions du TI15",
    description:
      "Analyse du compendium de The International 2026 : emblèmes de War Banner par rôle, projection de points du Fantasy Draft, probabilités du système suisse, ratings Glicko-2 et pages d'équipes, de joueurs et de matchs à partir des données OpenDota.",
    headline: "Analyse du compendium de The International 2026",
    intro:
      "Deux choses décident de la plupart des points perdus dans le compendium : quels emblèmes placer sur la War Banner de chaque rôle, et comment répartir les pronostics de la phase de groupes. Les deux sont calculées à partir des vrais matchs des équipes sur OpenDota, pas d'après la grille de prix du glossaire.",
    features: [
      "Emblèmes de War Banner pour Core Duo, Mid et Support Duo — toutes les combinaisons testées, traits compris",
      "Votre propre inventaire d'emblèmes : laquelle des seize équipes transforme vos rolls en le plus de points",
      "Projection de points du Fantasy Draft sur la période, avec plafond, plancher et dispersion par map",
      "Probabilités des cases du suisse et une grille de pronostics optimisée pour l'espérance de points",
      "Coaching Titles classés selon ce qu'ils rapportent vraiment, pas selon le pourcentage affiché",
      "Pages d'équipes, de joueurs et de matchs : statistiques OpenDota, pool de héros, rating Glicko-2 et notre analyse",
    ],
    teamsHeading: "Équipes de The International 2026",
    teamsNote:
      "Chaque équipe a une page avec ses matchs, ses moyennes par map, son pool de héros et un découpage par rôle.",
    loading: "Chargement des données…",
  },
  pl: {
    title: "Compendium Analyzer — Fantasy i Predictions na TI15",
    description:
      "Analityka kompendium The International 2026: emblematy War Banner według ról, prognoza punktów Fantasy Draft, prawdopodobieństwa systemu szwajcarskiego, ratingi Glicko-2 oraz strony drużyn, graczy i meczów na danych OpenDota.",
    headline: "Analityka kompendium The International 2026",
    intro:
      "O większości punktów traconych w kompendium decydują dwie rzeczy: jakie emblematy trafią na War Banner każdej roli i jak rozłożyć typy fazy grupowej. Obie liczone są z prawdziwych meczów uczestników w OpenDota, a nie z cennika w glosariuszu.",
    features: [
      "Emblematy War Banner dla Core Duo, Mid i Support Duo — sprawdzana każda kombinacja, razem z cechami",
      "Własny ekwipunek emblematów: która z szesnastu drużyn zamieni twoje rolle w najwięcej punktów",
      "Prognoza punktów Fantasy Draft na okres — z sufitem, podłogą i rozrzutem na mapę",
      "Prawdopodobieństwa pól systemu szwajcarskiego i gotowy układ typów pod maksimum oczekiwanych punktów",
      "Coaching Titles ustawione według tego, ile naprawdę dają, a nie ile mają wypisane",
      "Strony drużyn, graczy i meczów: statystyki OpenDota, pula bohaterów, rating Glicko-2 i nasza analiza",
    ],
    teamsHeading: "Drużyny The International 2026",
    teamsNote:
      "Każda drużyna ma stronę z meczami, średnimi na mapę, pulą bohaterów i rozbiciem na role.",
    loading: "Wczytuję dane…",
  },
  tr: {
    title: "Compendium Analyzer — TI15 Fantasy ve Predictions",
    description:
      "The International 2026 kompendium analizi: role göre War Banner amblemleri, Fantasy Draft puan öngörüsü, İsviçre sistemi olasılıkları, Glicko-2 ratingleri ve OpenDota verisiyle hazırlanan takım, oyuncu ve maç sayfaları.",
    headline: "The International 2026 kompendium analizi",
    intro:
      "Kompendiumda kaybedilen puanların çoğunu iki şey belirler: her rolün War Banner'ına hangi amblemlerin konduğu ve grup aşaması tahminlerinin nasıl dizildiği. İkisi de sözlükteki puan listesinden değil, katılımcı takımların OpenDota'daki gerçek maçlarından hesaplanır.",
    features: [
      "Core Duo, Mid ve Support Duo için War Banner amblemleri — bütün kombinasyonlar, özellikler dâhil",
      "Kendi amblem envanterin: on altı takımdan hangisi senin atışlarını en çok puana çeviriyor",
      "Dönem için Fantasy Draft puan öngörüsü; tavan, taban ve maç başına dağılımla birlikte",
      "İsviçre sistemi kutu olasılıkları ve beklenen puana göre optimize edilmiş hazır tahmin dizilimi",
      "Coaching Titles, üzerinde yazan yüzdeye göre değil, gerçekte ne kazandırdığına göre sıralanır",
      "Takım, oyuncu ve maç sayfaları: OpenDota istatistikleri, kahraman havuzu, Glicko-2 rating ve kendi analizimiz",
    ],
    teamsHeading: "The International 2026 takımları",
    teamsNote:
      "Her takımın maçlarını, maç başına ortalamalarını, kahraman havuzunu ve rol rol dökümünü gösteren bir sayfası var.",
    loading: "Veriler yükleniyor…",
  },
  id: {
    title: "Compendium Analyzer — Fantasy dan Predictions TI15",
    description:
      "Analitik compendium The International 2026: emblem War Banner per peran, proyeksi poin Fantasy Draft, probabilitas sistem Swiss, rating Glicko-2, serta halaman tim, pemain, dan pertandingan dari data OpenDota.",
    headline: "Analitik compendium The International 2026",
    intro:
      "Dua hal menentukan sebagian besar poin yang hilang di compendium: emblem mana yang dipasang di War Banner tiap peran, dan bagaimana tebakan fase grup disusun. Keduanya dihitung dari pertandingan nyata para peserta di OpenDota, bukan dari daftar harga di glosarium.",
    features: [
      "Emblem War Banner untuk Core Duo, Mid, dan Support Duo — semua kombinasi dicek, termasuk trait",
      "Inventaris emblem Anda sendiri: tim mana dari enam belas tim yang mengubah hasil roll Anda jadi poin terbanyak",
      "Proyeksi poin Fantasy Draft untuk satu periode, lengkap dengan batas atas, batas bawah, dan sebaran per map",
      "Probabilitas kotak sistem Swiss dan susunan tebakan yang sudah dioptimalkan untuk ekspektasi poin",
      "Coaching Titles diurutkan menurut hasil nyatanya, bukan menurut persentase yang tertulis",
      "Halaman tim, pemain, dan pertandingan: statistik OpenDota, kolam hero, rating Glicko-2, dan analisis kami",
    ],
    teamsHeading: "Tim peserta The International 2026",
    teamsNote:
      "Setiap tim punya halaman berisi pertandingannya, rata-rata per map, kolam hero, dan rincian per peran.",
    loading: "Memuat data…",
  },
  vi: {
    title: "Compendium Analyzer — Fantasy và Predictions cho TI15",
    description:
      "Phân tích compendium The International 2026: huy hiệu War Banner theo vai trò, dự phóng điểm Fantasy Draft, xác suất thể thức Thụy Sĩ, rating Glicko-2 cùng trang đội, tuyển thủ và trận đấu dựng từ dữ liệu OpenDota.",
    headline: "Phân tích compendium The International 2026",
    intro:
      "Phần lớn số điểm bị mất trong compendium do hai việc quyết định: đặt huy hiệu nào lên War Banner của từng vai trò, và xếp dự đoán vòng bảng ra sao. Cả hai đều được tính từ các trận thật của những đội dự giải trên OpenDota, chứ không phải từ bảng giá trong phần chú giải.",
    features: [
      "Huy hiệu War Banner cho Core Duo, Mid và Support Duo — thử mọi tổ hợp, tính cả trait",
      "Kho huy hiệu của riêng bạn: trong mười sáu đội, đội nào biến số huy hiệu ấy thành nhiều điểm nhất",
      "Dự phóng điểm Fantasy Draft cho cả giai đoạn, kèm mức trần, mức sàn và độ dao động từng ván",
      "Xác suất các ô của thể thức Thụy Sĩ và một phương án dự đoán đã tối ưu theo kỳ vọng điểm",
      "Coaching Titles xếp theo mức thực nhận, không theo phần trăm ghi trên danh hiệu",
      "Trang đội, tuyển thủ và trận đấu: số liệu OpenDota, kho hero, rating Glicko-2 và phân tích của chúng tôi",
    ],
    teamsHeading: "Các đội dự The International 2026",
    teamsNote:
      "Mỗi đội đều có trang riêng với danh sách trận, số trung bình mỗi ván, kho hero và phần bóc tách theo vai trò.",
    loading: "Đang tải dữ liệu…",
  },
};
