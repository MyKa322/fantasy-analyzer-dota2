"""Картинки страницы для соцсетей и поисковой выдачи (og:image).

Собираются скриптом, а не рисуются руками, по той же причине, что и манифесты:
меняется название или адрес — картинки пересобираются одной командой, и в них
не остаётся вчерашнего текста.

На каждый язык своя картинка: превью в Telegram и в поиске — это первое, что
человек видит, и русская подпись под английской ссылкой сразу говорит, что
страницу переводили наполовину.

Размер 1200x630 — то, что ждут Telegram, Discord, X и превью в поиске. Весь
текст держится в безопасной зоне с большими полями: у карточек меньшего
формата края обрезаются.

    python backend/tools/build_og_image.py
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "frontend" / "public" / "assets" / "emblems"
OUTPUT_DIR = ROOT / "frontend" / "public"

WIDTH, HEIGHT = 1200, 630
BACKGROUND = "#14161c"
PANEL = "#1a1d24"
GOLD = "#c8a24a"
TEXT = "#e5e5e5"
MUTED = "#8b93a0"

SITE = "myka322.github.io/fantasy-analyzer-dota2"

# Те же эмблемы, что показывает баннер саппорта, — три цвета сразу, чтобы по
# картинке было видно, о чём страница.
EMBLEMS = (
    "fantasy_emblem_wards_placed_png.webp",
    "fantasy_emblem_creeps_stacked_png.webp",
    "fantasy_emblem_teamfight_png.webp",
    "fantasy_emblem_roshan_png.webp",
    "fantasy_emblem_kills_png.webp",
    "fantasy_emblem_gpm_png.webp",
)

# Тексты повторяют описание страницы, но короче: в карточку помещается три
# строки, и это должны быть слова, по которым понятно, что здесь считают.
CARDS = {
    "ru": {
        "file": "og.png",
        "lead": "Fantasy Draft и Predictions по реальным матчам",
        "details": (
            "Подбор эмблем War Banner · прогноз очков роли\n"
            "вероятности корзин Swiss · страницы команд и игроков"
        ),
    },
    "en": {
        "file": "og-en.png",
        "lead": "Fantasy Draft and Predictions from real matches",
        "details": (
            "War Banner emblem picks · role point projection\n"
            "Swiss bucket odds · team and player pages"
        ),
    },
    "uk": {
        "file": "og-uk.png",
        "lead": "Fantasy Draft і Predictions за реальними матчами",
        "details": (
            "Добір емблем War Banner · прогноз очок ролі\n"
            "імовірності кошиків Swiss · сторінки команд і гравців"
        ),
    },
    "zh": {
        "file": "og-zh.png",
        "lead": "基于真实比赛的梦幻联赛与赛果预测",
        "details": ("战旗纹章搭配 · 位置得分预测\n瑞士轮分组概率 · 战队与选手主页"),
    },
    "es": {
        "file": "og-es.png",
        "lead": "Fantasy Draft y Predictions a partir de partidas reales",
        "details": (
            "Emblemas del War Banner · proyección de puntos por rol\n"
            "probabilidades de casillas Swiss · páginas de equipos y jugadores"
        ),
    },
    "pt": {
        "file": "og-pt.png",
        "lead": "Fantasy Draft e Predictions a partir de partidas reais",
        "details": (
            "Emblemas do War Banner · projeção de pontos por função\n"
            "probabilidades das casas do suíço · páginas de times e jogadores"
        ),
    },
    "de": {
        "file": "og-de.png",
        "lead": "Fantasy Draft und Predictions aus echten Spielen",
        "details": (
            "War-Banner-Embleme · Punkteprojektion je Rolle\n"
            "Wahrscheinlichkeiten im Schweizer System · Team- und Spielerseiten"
        ),
    },
    "fr": {
        "file": "og-fr.png",
        "lead": "Fantasy Draft et Predictions à partir de vrais matchs",
        "details": (
            "Emblèmes de la War Banner · projection de points par rôle\n"
            "probabilités des cases suisses · pages d'équipes et de joueurs"
        ),
    },
    "pl": {
        "file": "og-pl.png",
        "lead": "Fantasy Draft i Predictions na podstawie prawdziwych meczów",
        "details": (
            "Emblematy War Banner · prognoza punktów roli\n"
            "prawdopodobieństwa pól szwajcarskich · strony drużyn i graczy"
        ),
    },
    "tr": {
        "file": "og-tr.png",
        "lead": "Gerçek maçlara dayalı Fantasy Draft ve Predictions",
        "details": (
            "War Banner amblemleri · rol başına puan öngörüsü\n"
            "İsviçre sistemi kutu olasılıkları · takım ve oyuncu sayfaları"
        ),
    },
    "id": {
        "file": "og-id.png",
        "lead": "Fantasy Draft dan Predictions dari pertandingan nyata",
        "details": (
            "Emblem War Banner · proyeksi poin per peran\n"
            "probabilitas kotak Swiss · halaman tim dan pemain"
        ),
    },
    "vi": {
        "file": "og-vi.png",
        "lead": "Fantasy Draft và Predictions từ các trận đấu thật",
        "details": (
            "Huy hiệu War Banner · dự phóng điểm theo vai trò\n"
            "xác suất các ô Thụy Sĩ · trang đội và tuyển thủ"
        ),
    },
}

# Шрифты Windows: bold для заголовка, обычный для остального. Для китайского
# нужен свой — в Segoe UI иероглифов нет, и вместо текста будут квадраты.
FONTS = {
    "bold": (
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "regular": (
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
    "cjk-bold": ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"),
    "cjk": ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc"),
}


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONTS[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    log.warning("шрифт %s не найден, беру встроенный", kind)
    return ImageFont.load_default()


def build(locale: str) -> Path:
    card = CARDS[locale]
    body = "cjk" if locale == "zh" else "regular"
    heading = "cjk-bold" if locale == "zh" else "bold"

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Полоса цвета компендиума сверху — она же отличает картинку от любой
    # другой тёмной превьюшки в ленте.
    draw.rectangle((0, 0, WIDTH, 6), fill=GOLD)

    draw.text((72, 96), "COMPENDIUM ANALYZER", font=_font("bold", 30), fill=GOLD)
    draw.text((WIDTH - 72, 110), SITE, font=_font("regular", 24), fill=MUTED, anchor="rm")

    draw.text((72, 156), "The International 2026", font=_font("bold", 78), fill=TEXT)
    draw.text((72, 258), str(card["lead"]), font=_font(body, 36), fill=TEXT)
    draw.text(
        (72, 322),
        str(card["details"]),
        font=_font(body, 29),
        fill=MUTED,
        spacing=12,
    )

    draw.rectangle((72, 470, WIDTH - 72, 471), fill="#2a2e3a")

    # Эмблемы в ряд внизу: они же стоят на карточках в интерфейсе.
    x = 72
    for name in EMBLEMS:
        path = ASSETS / name
        if not path.exists():
            log.warning("нет эмблемы %s — пропускаю", name)
            continue
        tile = Image.open(path).convert("RGBA").resize((72, 72), Image.LANCZOS)
        draw.rounded_rectangle((x - 8, 502, x + 80, 590), radius=8, fill=PANEL)
        image.paste(tile, (x, 510), tile)
        x += 104

    output = OUTPUT_DIR / str(card["file"])
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    return output


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    for locale in CARDS:
        path = build(locale)
        log.info("%s -> %s (%.0f КБ)", locale, path.name, path.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
