"""Проверка документации на расхождение (04.08).

Зачем. Документы в `docs/` пишет ассистент, у которого память обнуляется
между сессиями: в начале дня он читает `Контекст_проекта.md`, но не держит
в голове полторы тысячи строк уроков и архива. Поэтому вывод, уже записанный
неделю назад, добавляется заново — не назло, а потому что не искался.
Заметить это может только тот, кто помнит оба текста целиком, то есть никто.

Скрипт не решает за человека — он показывает КАНДИДАТОВ:
  1. похожие абзацы (между файлами и внутри одного);
  2. битые перекрёстные ссылки;
  3. задачи, закрытые в `Реализовано.md`, но живые в `План_реализации.md`;
  4. разделы, переросшие лимит (признак, что случай смешался с правилом).

Запуск из `backend/`:  python scripts/docs_audit.py
Полный список кандидатов: python scripts/docs_audit.py --all

⚠ Путь к `docs/` считается от МЕСТА СКРИПТА, а не от текущей папки.
Это те же грабли, что в з.105: скрипт, запущенный из другой директории,
молча смотрел не туда и печатал «0 записей». Пустой результат обязан
означать «чисто», а не «не нашёл файлы».
"""

from __future__ import annotations

import re
import sys
import unicodedata
from itertools import combinations
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"

# --- пороги -----------------------------------------------------------------
# Подобраны на переборке 04.08: при 0.60 находились все семь настоящих пар
# и три законных пересечения (перечисления команд). Ниже 0.5 отчёт тонет
# в шуме, выше 0.7 — пропускает пересказ своими словами.
SIMILARITY = 0.60
SHINGLE = 4            # длина словесной n-граммы
MIN_WORDS = 20         # абзацы короче не сравниваем: совпадут случайно

# Лимиты размера. Не эстетика: раздел, переросший их, на переборке 04.08
# каждый раз оказывался смесью правила и разбора случая.
# ⚠ Считаются только строки ПРОЗЫ: таблицы и блоки кода бывают длинными
# по делу (сравнение «что показала проверка / что было на самом деле»),
# и штрафовать за них — значит подталкивать выбрасывать полезное.
LIMITS = {"Уроки.md": 18, "Архив_решений.md": 45}

FILES = ["Уроки.md", "Архив_решений.md", "План_реализации.md", "Реализовано.md"]


# --- разбор -----------------------------------------------------------------

def normalize(text: str) -> list[str]:
    """Слова без разметки, регистра и ё/е — сравниваем смысл, а не запись."""
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    text = re.sub(r"`[^`]*`", " ", text)          # код не показателен
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def shingles(words: list[str]) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def paragraphs(path: Path) -> list[tuple[str, str]]:
    """Абзацы файла как (заголовок раздела, текст)."""
    out, section = [], "—"
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        head = re.match(r"^#{2,4}\s+(.+)$", block.splitlines()[0])
        if head:
            section = head.group(1).strip()
        # таблицы и списки команд сравнивать бессмысленно
        if block.lstrip().startswith(("|", "```")):
            continue
        out.append((section, block))
    return out


def sections(path: Path) -> list[tuple[str, int]]:
    """Разделы `### …` и их длина в строках ПРОЗЫ.

    Пустые строки, таблицы и блоки кода не считаются: длинная таблица
    сравнения — это польза, а не разбухание.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    marks = [(i, ln[4:].strip()) for i, ln in enumerate(lines) if ln.startswith("### ")]
    out = []
    for n, (start, title) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        prose, in_code = 0, False
        for line in lines[start + 1:end]:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not stripped or stripped.startswith("|"):
                continue
            prose += 1
        out.append((title, prose))
    return out


# --- проверки ---------------------------------------------------------------

def check_similar(show_all: bool) -> list[str]:
    items = []
    for name in FILES:
        path = DOCS / name
        if not path.exists():
            continue
        for section, text in paragraphs(path):
            words = normalize(text)
            if len(words) >= MIN_WORDS:
                items.append((name, section, text, shingles(words)))

    found = []
    for (f1, s1, t1, sh1), (f2, s2, t2, sh2) in combinations(items, 2):
        score = jaccard(sh1, sh2)
        if score < SIMILARITY:
            continue
        where = f"{f1} → «{s1}»" if f1 == f2 else f"{f1} «{s1}»  ↔  {f2} «{s2}»"
        line = f"  {score:.0%}  {where}"
        if show_all:
            line += f"\n        {t1.splitlines()[0][:90]}…"
        found.append(line)
    return found


def check_links() -> list[str]:
    bad = []
    lessons = DOCS / "Уроки.md"
    archive = DOCS / "Архив_решений.md"
    if not (lessons.exists() and archive.exists()):
        return bad

    ltext = lessons.read_text(encoding="utf-8")
    atext = archive.read_text(encoding="utf-8")

    numbers = set(re.findall(r"^### (\d+\.\d+)", ltext, re.M))
    for ref in set(re.findall(r"→ Уроки ([\d.]+)", atext)):
        if ref.rstrip(".") not in numbers:
            bad.append(f"  Архив → Уроки {ref}: такого пункта нет")

    titles = [t.strip().lower() for t in re.findall(r"^### (.+)$", atext, re.M)]
    for ref in set(re.findall(r"`Архив_решений\.md` → «([^»]+)»", ltext)):
        key = ref.split(":")[0].strip().lower()
        if not any(key in t for t in titles):
            bad.append(f"  Уроки → Архив «{ref}»: такого раздела нет")
    return bad


def check_ghost_tasks() -> list[str]:
    """Задача, закрытая в хронике, но оставшаяся в бэклоге как открытая."""
    plan, done = DOCS / "План_реализации.md", DOCS / "Реализовано.md"
    if not (plan.exists() and done.exists()):
        return []

    open_ids = set(re.findall(r"^\*\*(\d+)\.\*\*", plan.read_text(encoding="utf-8"), re.M))
    closed = set()
    for row in done.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in row.split("|")]
        if len(cells) > 3 and cells[2].isdigit():
            closed.add(cells[2])

    return [f"  задача {n} закрыта в Реализовано.md, но осталась в бэклоге"
            for n in sorted(open_ids & closed, key=int)]


def check_size() -> list[str]:
    out = []
    for name, limit in LIMITS.items():
        path = DOCS / name
        if not path.exists():
            continue
        for title, length in sections(path):
            if length > limit:
                out.append(f"  {name} «{title}» — {length} строк (лимит {limit})")
    return out


# --- вывод ------------------------------------------------------------------

def main() -> int:
    if not DOCS.is_dir():
        # Громко, а не «0 находок»: отсутствие папки — это отказ инструмента,
        # а не чистый результат (урок «инструмент должен падать»).
        print(f"НЕ НАЙДЕНА папка документов: {DOCS}", file=sys.stderr)
        return 2

    show_all = "--all" in sys.argv
    blocks = [
        ("Похожие абзацы — кандидаты в дубли", check_similar(show_all)),
        ("Битые перекрёстные ссылки", check_links()),
        ("Задачи-призраки", check_ghost_tasks()),
        ("Разделы сверх лимита (случай смешался с правилом?)", check_size()),
    ]

    total = 0
    for title, found in blocks:
        print(f"\n{title}: {len(found)}")
        if found:
            shown = found if show_all else found[:10]
            print("\n".join(shown))
            if len(found) > len(shown):
                print(f"  … ещё {len(found) - len(shown)}, полный список: --all")
        total += len(found)

    print(f"\nВсего находок: {total}")
    print("⚠ Это КАНДИДАТЫ. Похожие абзацы бывают законно похожими —")
    print("  решает человек. Скрипт только сокращает место для поиска.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
