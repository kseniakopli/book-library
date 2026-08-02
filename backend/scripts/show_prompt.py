"""Показать РЕАЛЬНЫЙ промпт, который уедет в модель для конкретной книги.

Зачем (02.08). Запрет по исполнителям не сработал: после четырёх перегенераций
Portishead выросла с 7 книг до 10, хотя лежала в списке запрета. Прежде чем
объяснять это поведением модели, надо убедиться, что запрет вообще доехал.

Отдельная причина не доверять глазам: `services/ai._build_with_context`
ловит TypeError и МОЛЧА зовёт билдер промпта без контекста. Задумано как
совместимость со старой сигнатурой приватного prompt_config.py, но на практике
любая ошибка внутри построения промпта превращается в тихую генерацию без
единого запрета — без исключения, без записи в лог.

Скрипт повторяет ровно тот путь, что и роутер: build_book_context →
_build_with_context → _with_style. Печатает промпт целиком либо только сводку.

Ничего не меняет и токенов не тратит. Запуск из backend/:
    python scripts/show_prompt.py --book=42
    python scripts/show_prompt.py --book=42 --category=design
    python scripts/show_prompt.py --book=42 --category=food --full

Категории: music, design, food, aroma.
"""

import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from models import Book
from prompt_config import (
    build_aroma_prompt,
    build_design_prompt,
    build_food_prompt,
    build_music_prompt,
)
from services.ai import _build_with_context, _with_style
from services.prompt_context import build_book_context
from sqlmodel import Session, select

BUILDERS = {
    "music": build_music_prompt,
    "design": build_design_prompt,
    "food": build_food_prompt,
    "aroma": build_aroma_prompt,
}

# Что ищем в готовом тексте промпта. Проверяем именно ИТОГОВУЮ строку, а не
# содержимое context: между ними стоит `_build_with_context`, который молча
# глотает TypeError и зовёт билдер без контекста вовсе.
CHECKS = {
    "music": [
        ("аннотация книги", "Аннотация книги"),
        ("список avoid (треки)", "уже примелькались в других книгах"),
        ("список avoid_artists", "НЕ бери у них"),
    ],
    "design": [
        ("аннотация книги", "Аннотация книги"),
        ("список avoid_fonts", "Эти шрифты уже стоят"),
        ("статистика палитр", "имеют ТЁПЛЫЙ светлый фон"),
    ],
    "food": [
        ("аннотация книги", "Аннотация книги"),
        ("список avoid (блюда)", "уже примелькались в других книгах"),
    ],
    "aroma": [
        ("аннотация книги", "Аннотация книги"),
        ("список avoid (ароматы)", "уже примелькались в других книгах"),
    ],
}

BOOK_ID = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--book=")), None)
CATEGORY = next(
    (a.split("=", 1)[1] for a in sys.argv if a.startswith("--category=")), "music"
)
FULL = "--full" in sys.argv


def main():
    with Session(database.engine) as session:
        if BOOK_ID:
            book = session.get(Book, BOOK_ID)
        else:
            book = session.exec(select(Book)).first()
        if book is None:
            print("Книга не найдена. Укажи --book=ID.")
            return

        user_id = 1  # контекст вкуса берётся по пользователю; для проверки хватит владельца
        context = build_book_context(session, book.id, CATEGORY, user_id)

    print(f"Книга {book.id}: «{book.title}» — {book.author}")
    print(f"Категория: {CATEGORY}\n")

    print("=== ЧТО СОБРАЛ build_book_context ===")
    for key, value in context.items():
        if isinstance(value, list):
            print(f"  {key}: {len(value)} шт.")
            for v in value[:5]:
                print(f"      - {v}")
            if len(value) > 5:
                print(f"      … ещё {len(value) - 5}")
        elif isinstance(value, str) and len(value) > 80:
            print(f"  {key}: {len(value)} символов")
        else:
            print(f"  {key}: {value!r}")

    builder = BUILDERS.get(CATEGORY)
    if builder is None:
        print(f"\nДля категории {CATEGORY} печать промпта не настроена.")
        return

    prompt = _with_style(_build_with_context(builder, book.title, book.author, "ru", context))

    # Главная проверка: доехали ли блоки запрета в ИТОГОВЫЙ текст.
    print("\n=== ЧТО ДОЕХАЛО ДО ПРОМПТА ===")
    for label, needle in CHECKS.get(CATEGORY, []):
        present = needle in prompt
        # «НЕТ» не всегда ошибка: пустая аннотация или отсутствие перекоса —
        # законные причины, поэтому подсказываем, где смотреть источник.
        mark = "ЕСТЬ" if present else "НЕТ  ← смотри блок контекста выше"
        print(f"  {label:32} {mark}")

    print(f"\nДлина промпта: {len(prompt)} символов")
    if FULL:
        print("\n" + "=" * 60)
        print(prompt)


if __name__ == "__main__":
    main()
