"""Authors (task 97): author + bookauthor

Автор становится сущностью, а не строкой: без этого нет страницы автора,
соавторы склеены в одно имя, а статистика рассыпается при любом расхождении
в написании.

Две колонки под имя — решение Ксении: 148 авторов в библиотеке записаны
кириллицей и двое латиницей (Ann Patchett, Joan Didion). `sort_key` —
нормализованное имя, уникальное: дубль автора нельзя завести даже случайно
при импорте.

⚠ `book.author` НЕ трогаем. Строка остаётся для показа, печатной карточки и
обратной совместимости API; связи добавляются рядом. Значит миграция
неразрушающая: `downgrade` удаляет только новые таблицы, данные книг целы.

⚠ Только create_table — никакого batch_alter_table: batch пересоздаёт таблицу
через DROP, а при включённом PRAGMA foreign_keys это каскадом сносит дочерние
строки (инцидент миграции 0005).

Заполняется отдельно: `python scripts/backfill_authors.py --dry-run`, затем без
флага. Миграция намеренно не переносит данные — разбор строк требует глаз
(«Аркадий и Борис Стругацкие» → два человека с одной фамилией).

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-28

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "author",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_ru", sa.String(), nullable=True),
        sa.Column("name_original", sa.String(), nullable=True),
        sa.Column("sort_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_author_sort_key", "author", ["sort_key"], unique=True)

    op.create_table(
        "bookauthor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["book_id"], ["book.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["author.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "author_id", name="uq_bookauthor_book_author"),
    )
    op.create_index("ix_bookauthor_book_id", "bookauthor", ["book_id"])
    op.create_index("ix_bookauthor_author_id", "bookauthor", ["author_id"])


def downgrade() -> None:
    op.drop_index("ix_bookauthor_author_id", table_name="bookauthor")
    op.drop_index("ix_bookauthor_book_id", table_name="bookauthor")
    op.drop_table("bookauthor")
    op.drop_index("ix_author_sort_key", table_name="author")
    op.drop_table("author")
