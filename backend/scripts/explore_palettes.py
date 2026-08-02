"""Разведка палитр паспортов оформления (задача 100, хвост 01.08).

Вопрос, на который отвечает скрипт: **насколько однообразны палитры, которые
выдаёт модель, и правда ли они «тёплые кремовые»** — или так только кажется
после того, как интерфейс уехал в холодный бордо.

Повод. После редизайна переход с главной на страницу книги стал резким.
Первая гипотеза была «генерацию чем-то ограничили», но в `build_design_prompt`
ограничений по гамме нет: модель выбирает цвет свободно. Значит либо она сама
сходится к одной гамме (то же, что з.99 с повторяющимися треками, только про
цвет), либо дело не в паспортах, а в том, что мы сдвинули фон под ними.
Отличить одно от другого можно только цифрами.

Ничего не меняет: только читает и печатает отчёт.

Запуск из папки backend/:
    python scripts/explore_palettes.py            # отчёт на экран
    python scripts/explore_palettes.py --csv      # + выгрузка palettes_report.csv
"""

import colorsys
import csv
import json
import sys
from collections import Counter

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from models import AISelection, Book
from sqlmodel import Session, select

TO_CSV = "--csv" in sys.argv

# --since=ГГГГ-ММ-ДД — считать только паспорта от этой даты.
# Понадобилось сразу же (01.08): после правки промпта пересобрали 10 паспортов
# из 201, и на общем отчёте эффект не читался — десятка растворилась в двух
# сотнях старых. Отчёт по всему корпусу отвечает на вопрос «какие палитры у нас
# есть», а спросить нужно было «какие палитры даёт НОВЫЙ промпт».
SINCE = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--since=")), None)

# Тон в градусах → человеческое имя. Границы грубые, задача — не точность,
# а увидеть, сходится ли всё в один сектор круга.
HUE_NAMES = [
    (15, "красный"), (45, "оранжевый"), (70, "жёлтый"), (100, "лаймовый"),
    (160, "зелёный"), (200, "бирюзовый"), (250, "синий"), (290, "фиолетовый"),
    (330, "пурпурный"), (361, "красный"),
]


def hex_to_hsl(value):
    v = (value or "").strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        return None
    try:
        r, g, b = (int(v[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, l * 100


def hue_name(h, s):
    # У серого тон бессмысленен: при низкой насыщенности круг ничего не значит.
    if s < 10:
        return "нейтральный (серый)"
    for edge, name in HUE_NAMES:
        if h < edge:
            return name
    return "красный"


def warm_or_cold(h, s):
    if s < 10:
        return "нейтральный"
    # Тёплый сектор — от красного до жёлто-зелёного; холодный — остальное.
    return "тёплый" if (h < 100 or h >= 330) else "холодный"


def bucket(value, size):
    return f"{int(value // size) * size}–{int(value // size) * size + size}"


def main():
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection, Book)
            .where(AISelection.book_id == Book.id)
            .where(AISelection.category == "design")
        ).all()

    if not rows:
        print("Паспортов в базе нет — генерация ни разу не отрабатывала?")
        return

    records = []
    broken = 0
    for sel, book in rows:
        try:
            payload = json.loads(sel.payload)
        except (ValueError, TypeError):
            broken += 1
            continue
        light = payload.get("palette_light") or payload.get("palette") or {}
        dark = payload.get("palette_dark") or {}
        rec = {
            "book_id": book.id,
            "title": book.title,
            "source": sel.source,
            "created": sel.created_at.date().isoformat() if sel.created_at else "",
            "light_bg": light.get("bg", ""),
            "light_accent": light.get("accent", ""),
            "dark_bg": dark.get("bg", ""),
            "dark_accent": dark.get("accent", ""),
            "title_font": payload.get("title_font", ""),
            "body_font": payload.get("body_font", ""),
        }
        records.append(rec)

    if SINCE:
        before = len(records)
        records = [r for r in records if r["created"] >= SINCE]
        print(f"Фильтр --since={SINCE}: {len(records)} паспортов из {before}.")
        if not records:
            print("Под фильтр ничего не попало — проверь дату.")
            return

    print(f"Паспортов: {len(records)}" + (f", нечитаемых payload: {broken}" if broken else ""))
    print()

    # --- Главный вопрос: сходится ли светлый фон в одну точку ---
    for field, label in (("light_bg", "СВЕТЛЫЙ ФОН"), ("light_accent", "АКЦЕНТ (светлая)"),
                         ("dark_bg", "ТЁМНЫЙ ФОН")):
        hsl = [(r, hex_to_hsl(r[field])) for r in records]
        hsl = [(r, v) for r, v in hsl if v]
        if not hsl:
            continue
        print(f"=== {label} ({len(hsl)} шт.) ===")

        temps = Counter(warm_or_cold(h, s) for _, (h, s, _) in hsl)
        total = sum(temps.values())
        for name, n in temps.most_common():
            print(f"  {name:12} {n:4}  {n * 100 // total:3}%")

        hues = Counter(hue_name(h, s) for _, (h, s, _) in hsl)
        print("  тон:      " + ", ".join(f"{k} {v}" for k, v in hues.most_common(5)))

        sats = Counter(bucket(s, 10) for _, (_, s, _) in hsl)
        print("  насыщ.:   " + ", ".join(f"{k}% {v}" for k, v in sorted(sats.items(), key=lambda x: -x[1])[:5]))

        exact = Counter(r[field].lower() for r, _ in hsl)
        repeats = [(c, n) for c, n in exact.most_common(5) if n > 1]
        if repeats:
            print("  ⚠ повторы точь-в-точь: " + ", ".join(f"{c} ×{n}" for c, n in repeats))
        print(f"  уникальных значений: {len(exact)} на {len(hsl)} книг")
        print()

    # --- Шрифты: та же болезнь может быть и здесь ---
    fonts = Counter(r["title_font"] for r in records if r["title_font"])
    print("=== ЗАГОЛОВОЧНЫЙ ШРИФТ ===")
    print(f"  уникальных: {len(fonts)} на {len(records)} книг")
    for name, n in fonts.most_common(8):
        print(f"  {name:28} {n}")
    print()

    # --- Разрез по источнику и по дате: менялось ли поведение со временем ---
    print("=== ПО ИСТОЧНИКУ ===")
    for src, n in Counter(r["source"] for r in records).most_common():
        print(f"  {src:10} {n}")
    print()
    print("=== ПО ДАТЕ ГЕНЕРАЦИИ ===")
    for day, n in sorted(Counter(r["created"] for r in records).items()):
        print(f"  {day}  {n}")

    if TO_CSV:
        out = "palettes_report.csv"
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            w.writeheader()
            w.writerows(records)
        print(f"\nВыгружено: {out}")


if __name__ == "__main__":
    main()
