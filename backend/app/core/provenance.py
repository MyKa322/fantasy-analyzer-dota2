"""Происхождение метрики: какой источник её дал и насколько ей можно верить.

До появления реплеев доступность стата была свойством самого стата: `STAT_SOURCES`
в `ingest/stat_mapping.py` — статическая витрина «мадстоуны OpenDota не отдаёт».
С двумя источниками это перестаёт быть правдой: мадстоуны недоступны *из OpenDota*,
но точны *из реплея*, и один и тот же матч может быть собран наполовину из одного,
наполовину из другого.

Поэтому доступность становится функцией пары (стат, источник), а у каждого
записанного значения появляется происхождение. Это и есть механизм, которым данные
реплея вытесняют данные API по одному полю за раз: не «перезаписать всё», а
«взять то, что известно точнее», с честной пометкой, откуда оно взялось.

Порядок предпочтения намеренно задан данными, а не порядком вызова: иначе
результат зависел бы от того, что подгрузилось первым, — а это ровно тот класс
багов, который потом не воспроизводится.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.ingest.stat_mapping import STAT_SOURCES, Availability, StatSource

# `STAT_SOURCES` исторически называется без источника в имени, но описывает
# именно OpenDota. Псевдоним фиксирует это в терминах, не ломая импорты.
OPENDOTA_STAT_SOURCES = STAT_SOURCES


class Source(StrEnum):
    """Откуда физически получено значение."""

    OPENDOTA = "opendota"
    """Агрегированный JSON матча из OpenDota API."""

    REPLAY = "replay"
    """Собственный разбор .dem-реплея."""


# Насколько источник «свой»: при равной доступности выигрывает реплей — его
# семантику мы контролируем сами и умеем чинить, в отличие от чужого поля.
SOURCE_PRIORITY: dict[Source, int] = {
    Source.OPENDOTA: 1,
    Source.REPLAY: 2,
}

# Насколько значение соответствует тому, что просит глоссарий.
AVAILABILITY_RANK: dict[Availability, int] = {
    Availability.UNAVAILABLE: 0,
    Availability.APPROXIMATE: 1,
    Availability.EXACT: 2,
}


def _replay_sources() -> dict[str, StatSource]:
    """Что даёт разбор реплея по каждому стату Fantasy-конфига.

    Реплей — первичная запись матча, поэтому почти всё в нём точно по построению.
    Исключение одно и оно принципиальное: `teamfight_participation`. Точная формула
    Valve не опубликована (см. `config/ti15_fantasy.yaml`), так что из реплея мы
    посчитаем *свою* долю участия — и назвать её точной было бы враньём. Из-за
    этого правило разрешения ниже оставит для неё значение OpenDota: чужой прокси,
    который хотя бы совпадает с тем, что видит игрок на сайте, честнее нашего.
    """
    replay: dict[str, StatSource] = {}
    for stat in STAT_SOURCES:
        if stat == "teamfight_participation":
            replay[stat] = StatSource(
                stat,
                Availability.APPROXIMATE,
                "своя метрика участия: формула Valve не раскрыта",
            )
            continue
        replay[stat] = StatSource(stat, Availability.EXACT, "событие из combat log реплея")
    return replay


REPLAY_STAT_SOURCES: dict[str, StatSource] = _replay_sources()

STAT_SOURCES_BY_SOURCE: dict[Source, dict[str, StatSource]] = {
    Source.OPENDOTA: OPENDOTA_STAT_SOURCES,
    Source.REPLAY: REPLAY_STAT_SOURCES,
}


@dataclass(frozen=True, slots=True)
class Provenance:
    """Происхождение одного записанного значения."""

    source: Source
    availability: Availability
    note: str = ""

    @property
    def is_usable(self) -> bool:
        """Можно ли вообще считать по этому значению.

        `UNAVAILABLE` — это ноль-заглушка, а не измеренный ноль. Разница
        существенная: проекция обязана сказать «оценить не могу», а не занизить
        игрока молча.
        """
        return self.availability is not Availability.UNAVAILABLE


def describe(stat: str, source: Source) -> Provenance:
    """Что известно о стате `stat`, если он получен из `source`."""
    table = STAT_SOURCES_BY_SOURCE[source]
    entry = table.get(stat)
    if entry is None:
        return Provenance(source, Availability.UNAVAILABLE, f"{stat}: нет в таблице {source}")
    return Provenance(source, entry.availability, entry.note)


def _score(provenance: Provenance) -> tuple[int, int]:
    return AVAILABILITY_RANK[provenance.availability], SOURCE_PRIORITY[provenance.source]


def best_source(stat: str, sources: frozenset[Source] | set[Source]) -> Provenance:
    """Какой из доступных источников считать основным для этого стата.

    Сравнение идёт сперва по доступности, потом по приоритету источника, поэтому
    точное значение из OpenDota никогда не проигрывает приблизительному из реплея.
    """
    if not sources:
        return Provenance(Source.OPENDOTA, Availability.UNAVAILABLE, "источников нет")
    return max((describe(stat, s) for s in sources), key=_score)


def merge_stats(
    base: dict[str, float],
    base_source: Source,
    overlay: dict[str, float],
    overlay_source: Source,
) -> tuple[dict[str, float], dict[str, Provenance]]:
    """Наложить один источник на другой по одному стату за раз.

    Возвращает значения и происхождение каждого из них. Ключи берутся из обоих
    словарей: набор статов конфига может отличаться от того, что умеет источник,
    и пропажа ключа — это тоже факт, который должен быть виден.
    """
    values: dict[str, float] = {}
    provenance: dict[str, Provenance] = {}

    for stat in set(base) | set(overlay):
        candidates: list[tuple[Provenance, float]] = []
        if stat in base:
            candidates.append((describe(stat, base_source), base[stat]))
        if stat in overlay:
            candidates.append((describe(stat, overlay_source), overlay[stat]))

        chosen_provenance, chosen_value = max(candidates, key=lambda c: _score(c[0]))
        values[stat] = chosen_value
        provenance[stat] = chosen_provenance

    return values, provenance


def unusable_stats(
    provenance: dict[str, Provenance], stats: tuple[str, ...] | list[str]
) -> list[str]:
    """Какие из перечисленных статов нечем оценить — для предупреждения в UI.

    Аналог `stat_mapping.missing_stats`, но отвечает про конкретный матч, а не про
    источник вообще: тот же баннер на распарсенном нами матче оценивается целиком,
    а на матче из одного лишь OpenDota — нет.
    """
    return [s for s in stats if not provenance.get(s, describe(s, Source.OPENDOTA)).is_usable]
