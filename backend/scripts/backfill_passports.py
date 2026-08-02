# Разовая batch-догенерация паспортов оформления (задача 73).
# Книги без паспорта (старые / из CSV) в символьном режиме полки показывают
# логотип-полумесяц вместо своего экслибриса. Скрипт находит такие книги и
# генерирует паспорт для каждой через Anthropic **Message Batches API** —
# вдвое дешевле обычных вызовов и одним пакетом.
#
# Схема ответа задаётся через tool use (input_schema = JSON-схема DesignResult) —
# так же надёжно, как structured outputs в синхронном пути.
#
# Запуск из backend/ (нужны .env с ANTHROPIC_API_KEY и prompt_config.py):
#   python backfill_passports.py --dry-run   # показать книги без паспорта
#   python backfill_passports.py             # создать батч и дождаться (тратит токены)
#
# Пересборка существующих паспортов (после правки промпта, 01.08):
#   python scripts/backfill_passports.py --regenerate --limit=10 --dry-run
#   python scripts/backfill_passports.py --regenerate --limit=10
# Книги витрины исключаются всегда: их палитры ушли в печатный тираж 28.07.
#
# Батч обрабатывается на стороне Anthropic асинхронно (обычно минуты, лимит 24ч);
# скрипт опрашивает статус и по завершении сохраняет паспорта.
import sys
import time

import anthropic
from dotenv import load_dotenv
from sqlmodel import Session, select

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from constants import SOURCE_CLAUDE
from models import AISelection, Book
from prompt_config import build_design_prompt
from services.prompt_context import build_book_context

# Владелец: паспорт — общая для книги вещь, но профиль вкуса берётся по юзеру.
USER_ID = 1
from services.atmosphere import CATEGORIES, replace_selections
from services.ai import _with_style
from services.ai_schemas import DesignResult, design_result_without, enforce_fonts

load_dotenv()
client = anthropic.Anthropic()

# Инструмент = «верни паспорт по этой схеме». tool_choice форсирует его вызов,
# модель отвечает строго по JSON-схеме DesignResult (палитры, шрифты, символ).
def design_tool(schema) -> dict:
    """Инструмент батча под КОНКРЕТНУЮ книгу: схема сужается затасканными
    шрифтами (02.08). Раньше здесь лежала одна общая схема на весь прогон,
    и массовая пересборка ушла бы с полным списком шрифтов — то есть ровно
    без того ограничения, ради которого затевалась."""
    return {
        "name": "design_passport",
        "description": (
            "Паспорт оформления книги: две палитры, шрифты, символ-экслибрис, statement."
        ),
        "input_schema": schema.model_json_schema(),
    }


def _books_without_passport(session) -> list[Book]:
    have = set(
        session.exec(
            select(AISelection.book_id).where(AISelection.category == "design")
        ).all()
    )
    return [b for b in session.exec(select(Book)).all() if b.id not in have]


# Задача 100, хвост 01.08: пересборка УЖЕ существующих паспортов после правки
# промпта. Отдельный режим, потому что риски другие — не «добавить недостающее»,
# а «переписать то, что человек уже видел».
#
# ⚠ Книги витрины исключаются ВСЕГДА. Печатный тираж 28.07 сделан с их нынешними
# палитрами, карточки на руках, и расхождение бумаги с экраном не откатить.
# Флага «включить витринные» нет намеренно: такую вещь нельзя сделать опечаткой.
def _books_to_regenerate(session, limit: int | None) -> list[Book]:
    from models import UserBook

    featured = set(
        session.exec(select(UserBook.book_id).where(UserBook.featured.is_(True))).all()
    )
    have = set(
        session.exec(
            select(AISelection.book_id).where(AISelection.category == "design")
        ).all()
    )
    books = [
        b for b in session.exec(select(Book)).all()
        if b.id in have and b.id not in featured
    ]
    books.sort(key=lambda b: b.id)
    return books[:limit] if limit else books


def main():
    dry = "--dry-run" in sys.argv
    regen = "--regenerate" in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])

    with Session(database.engine) as session:
        if regen:
            targets = _books_to_regenerate(session, limit)
        else:
            targets = _books_without_passport(session)
        info = {b.id: (b.title, b.author) for b in targets}

    if regen:
        print(f"Книг к ПЕРЕСБОРКЕ паспорта: {len(targets)}"
              + (f" (ограничение --limit={limit})" if limit else "")
              + "\nКниги витрины исключены — их палитры ушли в печать.")
    else:
        print(f"Книг без паспорта: {len(targets)}")
    if dry:
        for bid, (t, a) in sorted(info.items()):
            print(f"  {bid}: {t} — {a}")
        print("\n--dry-run: батч не создавался.")
        return
    if not targets:
        return

    # Контекст считается ДО батча и по одному разу на книгу: внутри он ходит
    # в базу за паспортами всех остальных книг, и делать это в цикле построения
    # запросов означало бы N прогонов по всей библиотеке.
    with Session(database.engine) as session:
        contexts = {
            b.id: build_book_context(session, b.id, "design", USER_ID)
            for b in targets
        }

    # 1) собираем запросы батча (по одному на книгу)
    requests = [
        {
            "custom_id": f"book-{b.id}",
            "params": {
                "model": "claude-sonnet-5",
                "max_tokens": 8000,
                "tools": [
                    design_tool(
                        design_result_without(
                            contexts[b.id].get("avoid_fonts"), seed=b.id
                        )
                    )
                ],
                "tool_choice": {"type": "tool", "name": "design_passport"},
                # ⚠ Контекст здесь ОБЯЗАТЕЛЕН (02.08): без него батч уходит
                # без запретов по шрифтам и без статистики палитр, то есть
                # ровно та массовая генерация, ради разнообразия которой всё
                # и затевалось, прошла бы по старым правилам. Раньше вызов был
                # без context — и это было незаметно, потому что промпт всё
                # равно строится и выглядит нормально.
                "messages": [
                    {"role": "user", "content": _with_style(
                        build_design_prompt(b.title, b.author, "ru", contexts[b.id])
                    )}
                ],
            },
        }
        for b in targets
    ]

    batch = client.messages.batches.create(requests=requests)
    print(f"Батч создан: {batch.id} ({len(requests)} книг). Ждём обработки…")

    # 2) опрашиваем статус до завершения
    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        print(f"  {b.processing_status}… {b.request_counts}")
        time.sleep(15)

    # 3) забираем результаты, валидируем и сохраняем
    ok = failed = 0
    for entry in client.messages.batches.results(batch.id):
        book_id = int(entry.custom_id.split("-", 1)[1])
        if entry.result.type != "succeeded":
            failed += 1
            print(f"  ✗ book {book_id}: {entry.result.type}")
            continue
        tool_input = next(
            (blk.input for blk in entry.result.message.content
             if blk.type == "tool_use"),
            None,
        )
        try:
            design = DesignResult(**tool_input) if tool_input else None
            # enum в схеме инструмента — подсказка, а не гарантия: модель может
            # вернуть запрещённый шрифт. Правим, а не выбрасываем паспорт.
            if design is not None:
                swaps = enforce_fonts(
                    design, contexts.get(book_id, {}).get("avoid_fonts"), book_id
                )
                for swap in swaps:
                    print(f"  ↻ book {book_id}: {swap}")
        except Exception as e:                       # невалидный/битый паспорт
            design = None
            print(f"  ✗ book {book_id}: валидация — {e}")
        if design is None:
            failed += 1
            continue
        # сохраняем через общий путь (с защитой из задачи 74)
        replace_selections(book_id, "design", CATEGORIES["design"], {SOURCE_CLAUDE: design})
        ok += 1
        print(f"  ✓ book {book_id}")

    print(f"\nГотово: паспортов создано {ok}, ошибок {failed}.")


if __name__ == "__main__":
    main()
