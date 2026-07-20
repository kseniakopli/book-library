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
from services.atmosphere import CATEGORIES, replace_selections
from services.ai import DesignResult, _with_style

load_dotenv()
client = anthropic.Anthropic()

# Инструмент = «верни паспорт по этой схеме». tool_choice форсирует его вызов,
# модель отвечает строго по JSON-схеме DesignResult (палитры, шрифты, символ).
DESIGN_TOOL = {
    "name": "design_passport",
    "description": "Паспорт оформления книги: две палитры, шрифты, символ-экслибрис, statement.",
    "input_schema": DesignResult.model_json_schema(),
}


def _books_without_passport(session) -> list[Book]:
    have = set(
        session.exec(
            select(AISelection.book_id).where(AISelection.category == "design")
        ).all()
    )
    return [b for b in session.exec(select(Book)).all() if b.id not in have]


def main():
    dry = "--dry-run" in sys.argv
    with Session(database.engine) as session:
        targets = _books_without_passport(session)
        info = {b.id: (b.title, b.author) for b in targets}

    print(f"Книг без паспорта: {len(targets)}")
    if dry:
        for bid, (t, a) in sorted(info.items()):
            print(f"  {bid}: {t} — {a}")
        print("\n--dry-run: батч не создавался.")
        return
    if not targets:
        return

    # 1) собираем запросы батча (по одному на книгу)
    requests = [
        {
            "custom_id": f"book-{b.id}",
            "params": {
                "model": "claude-sonnet-5",
                "max_tokens": 8000,
                "tools": [DESIGN_TOOL],
                "tool_choice": {"type": "tool", "name": "design_passport"},
                "messages": [
                    {"role": "user", "content": _with_style(
                        build_design_prompt(b.title, b.author, "ru")
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
