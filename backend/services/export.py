# Экспорт полки в CSV (задачи 35 и 42).
#
# Формат намеренно совпадает с тем, что понимает импорт (STANDARD_COLUMNS
# в routers/imports.py): выгруженный файл можно вернуть обратно — в другой
# аккаунт, после переустановки, в чужой сервис. Круг замкнут, и это даёт
# импорту бесплатный контрольный образец: если экспорт не читается нашим же
# импортом, сломан один из двух, и тест это ловит.
#
# ⚠ Задача 42: CSV открывают в Excel/LibreOffice, а там ячейка, начинающаяся
# с `=`, `+`, `-` или `@`, — это ФОРМУЛА. Название книги вроде `=cmd|...`
# в чужой таблице превращается в исполняемую строку. Поэтому все текстовые
# значения проходят через _sanitize.
import csv
import io
from datetime import date

from sqlmodel import Session, select

from constants import STATUS_READ, STATUS_READING, STATUS_WANT
from models import Book, UserBook

# Заголовки — ровно те, что импорт распознаёт без AI.
# «Статус» сверх набора: импорт его игнорирует (выводит статус из оценки
# и даты), но человеку в таблице он нужен — иначе «хочу прочитать» и «читаю»
# в выгрузке неразличимы.
COLUMNS = ["Название", "Автор", "Моя оценка", "Дата прочтения", "ISBN", "Статус"]

STATUS_LABELS = {
    STATUS_READ: "Прочитана",
    STATUS_READING: "Читаю",
    STATUS_WANT: "Хочу прочитать",
}

# Символы, с которых табличный редактор начинает разбор формулы.
# \t и \r — потому что ими можно «сдвинуть» значение в соседнюю ячейку.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Excel на Windows определяет кодировку по BOM: без него кириллица
# открывается кракозябрами. Наш импорт читает utf-8-sig, BOM ему не мешает.
BOM = "﻿"

# Разделитель `;` — как у LiveLib и как ждёт Excel в русской локали.
# Импорт определяет разделитель сам (по заголовку), так что совместимости
# это не ломает.
DELIMITER = ";"


def _sanitize(value: str | None) -> str:
    """Обезвредить ячейку перед записью в CSV (задача 42).

    Опасное значение не режем и не выбрасываем — предваряем апострофом:
    так табличный редактор показывает его текстом, а данные не теряются.
    Апостроф — это соглашение Excel/LibreOffice, при обратном импорте
    его снимает _desanitize.
    """
    if value is None:
        return ""
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def desanitize(value: str | None) -> str | None:
    """Снять защитный апостроф при обратном импорте.

    Снимаем ТОЛЬКО если следом идёт опасный символ, то есть апостроф там
    заведомо наш: название, честно начинающееся с апострофа, не трогаем.
    """
    if value and value.startswith("'") and value[1:].startswith(FORMULA_PREFIXES):
        return value[1:]
    return value


def _fmt_date(value) -> str:
    """Дата в ISO — этот формат parse_read_date разбирает первым."""
    return value.strftime("%Y-%m-%d") if value else ""


def shelf_rows(session: Session, user_id: int) -> list[list[str]]:
    """Строки полки для выгрузки: прочитанные сначала (по дате, свежие сверху),
    затем остальные. Порядок для человека, импорт от него не зависит."""
    rows = session.exec(
        select(
            Book.title,
            Book.author,
            Book.isbn,
            UserBook.status,
            UserBook.rating,
            UserBook.read_at,
        )
        .join(UserBook, UserBook.book_id == Book.id)
        .where(UserBook.user_id == user_id)
    ).all()

    def order(row):
        # None-даты не сравниваются с datetime — отправляем их в конец
        # отдельным ключом (`is None`), а не подстановкой «нулевой» даты:
        # книга без даты не должна выглядеть прочитанной в 1970 году
        return (
            0 if row.status == STATUS_READ else 1,
            row.read_at is None,
            -row.read_at.timestamp() if row.read_at else 0,
        )

    return [
        [
            _sanitize(title),
            _sanitize(author),
            str(rating) if rating is not None else "",
            _fmt_date(read_at),
            _sanitize(isbn),
            STATUS_LABELS.get(status, status),
        ]
        for title, author, isbn, status, rating, read_at in sorted(rows, key=order)
    ]


def shelf_to_csv(session: Session, user_id: int) -> str:
    """Готовый текст CSV-файла (с BOM)."""
    buffer = io.StringIO()
    # lineterminator задаём явно: по умолчанию csv пишет \r\n, а StringIO
    # на разных платформах ведёт себя по-разному — фиксируем RFC 4180.
    writer = csv.writer(buffer, delimiter=DELIMITER, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerows(shelf_rows(session, user_id))
    return BOM + buffer.getvalue()


def export_filename(today: date | None = None) -> str:
    """Имя файла с датой: выгрузки копятся в «Загрузках», и без даты
    их не отличить друг от друга."""
    today = today or date.today()
    return f"nocturne-shelf-{today:%Y-%m-%d}.csv"
