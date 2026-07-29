"""Разведка строк авторов — подготовка к таблице авторов (задача 97).

Вопрос, на который отвечает скрипт: **по каким правилам разбирать
`Book.author`**, чтобы завести отдельных авторов и страницы для них.
Правила должны быть написаны под реальные данные, а не под догадки: запятая
обычно разделяет соавторов, но «Гамсун, Кнут» — это один человек в формате
«фамилия, имя», и автоматика молча наломает дров.

Ничего не меняет: только читает и печатает отчёт.

Запуск из папки backend/:
    python scripts/explore_authors.py           # отчёт на экран
    python scripts/explore_authors.py --all     # + полный список строк авторов
    python scripts/explore_authors.py --csv     # выгрузка в authors_report.csv
"""

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from models import Book
from sqlmodel import Session, select

SHOW_ALL = "--all" in sys.argv
TO_CSV = "--csv" in sys.argv

CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
LATIN = re.compile(r"[a-zA-Z]")
INITIALS = re.compile(r"\b[А-ЯA-Z]\.\s*[А-ЯA-Z]?\.?")
# разделители, которыми в одной строке могут быть склеены соавторы
SEPARATORS = {
    "запятая": re.compile(r","),
    "точка с запятой": re.compile(r";"),
    "слэш": re.compile(r"/"),
    "амперсанд": re.compile(r"&"),
    "союз «и»": re.compile(r"\sи\s"),
    "and": re.compile(r"\sand\s", re.I),
}


def norm_key(name: str) -> str:
    """Ключ для поиска ОДНОГО автора, записанного по-разному.

    Регистр, лишние пробелы, точки в инициалах и ё/е — не различия, а шум.
    Ключ намеренно грубый: его задача — собрать кандидатов на слияние, решение
    остаётся за человеком.
    """
    text = unicodedata.normalize("NFKC", name).lower().replace("ё", "е")
    text = text.replace(".", " ").replace(" ", " ")
    return " ".join(text.split())


def looks_like_surname_first(part: str) -> bool:
    """«Гамсун, Кнут» — один человек, а не два: слева и справа по одному слову."""
    left, _, right = part.partition(",")
    return bool(right) and len(left.split()) == 1 and len(right.split()) == 1


def main() -> None:
    with Session(database.engine) as session:
        books = session.exec(select(Book)).all()

    raw = [(b.id, (b.author or "").strip()) for b in books]
    empty = [bid for bid, a in raw if not a]
    authors = [a for _, a in raw if a]
    unique = sorted(set(authors))

    print(f"Книг: {len(raw)}   строк авторов: {len(authors)}   уникальных: {len(unique)}")
    if empty:
        print(f"⚠ Без автора: {len(empty)} книг (id: {empty[:10]}…)")

    # --- 1. Чем склеены соавторы ---
    print("\n--- разделители внутри строки ---")
    for label, pattern in SEPARATORS.items():
        hits = [a for a in unique if pattern.search(a)]
        if hits:
            print(f"{label:>16}: {len(hits):>3}   например: {hits[0]}")

    # --- 2. Запятая: соавторы или «фамилия, имя» ---
    with_comma = [a for a in unique if "," in a]
    surname_first = [a for a in with_comma if looks_like_surname_first(a)]
    coauthors = [a for a in with_comma if a not in surname_first]
    print("\n--- строки с запятой ---")
    print(f"всего: {len(with_comma)}")
    print(f"похоже на «фамилия, имя» (НЕ разбивать): {len(surname_first)}")
    for a in surname_first[:10]:
        print(f"    {a}")
    print(f"похоже на соавторов (разбивать): {len(coauthors)}")
    for a in coauthors[:10]:
        print(f"    {a}")

    # --- 3. Алфавит: кандидаты в name_ru и name_original ---
    cyr = [a for a in unique if CYRILLIC.search(a) and not LATIN.search(a)]
    lat = [a for a in unique if LATIN.search(a) and not CYRILLIC.search(a)]
    mixed = [a for a in unique if CYRILLIC.search(a) and LATIN.search(a)]
    print("\n--- алфавит (решение: хранить имя по-русски и в оригинале) ---")
    print(f"кириллица: {len(cyr)}   латиница: {len(lat)}   смешанные: {len(mixed)}")
    if lat:
        print("латиницей записаны (кандидаты в оригинальное имя):")
        for a in lat[:15]:
            print(f"    {a}")
    for a in mixed[:5]:
        print(f"  ⚠ смешанная строка: {a}")

    # --- 4. Инициалы ---
    with_initials = [a for a in unique if INITIALS.search(a)]
    if with_initials:
        print(f"\n--- с инициалами: {len(with_initials)} ---")
        for a in with_initials[:10]:
            print(f"    {a}")

    # --- 5. Разное написание одного автора ---
    by_key = defaultdict(list)
    for a in unique:
        by_key[norm_key(a)].append(a)
    variants = {k: v for k, v in by_key.items() if len(v) > 1}
    print(f"\n--- один автор, разные написания: {len(variants)} ---")
    for key, names in list(variants.items())[:10]:
        print(f"    {names}")
    if not variants:
        print("    не нашлось — но это только точные совпадения после нормализации;")
        print("    «Ann Patchett» и «Энн Пэтчетт» так не связать, нужен ручной разбор")

    # --- 6. Кто чаще всего встречается ---
    print("\n--- топ строк (сколько книг) ---")
    for name, count in Counter(authors).most_common(15):
        print(f"{count:>3}  {name}")

    if SHOW_ALL:
        print("\n--- все строки авторов ---")
        for a in unique:
            print(f"    {a}")

    if TO_CSV:
        path = "authors_report.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["строка автора", "книг", "ключ", "запятая", "алфавит"])
            counts = Counter(authors)
            for a in unique:
                alphabet = (
                    "смешанный" if a in mixed
                    else "латиница" if a in lat
                    else "кириллица"
                )
                comma = (
                    "фамилия, имя" if a in surname_first
                    else "соавторы" if a in coauthors
                    else ""
                )
                writer.writerow([a, counts[a], norm_key(a), comma, alphabet])
        print(f"\nВыгружено: {path} (разделитель «;», открывается Excel)")


if __name__ == "__main__":
    main()
