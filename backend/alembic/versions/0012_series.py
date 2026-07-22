"""Series + UserSeries (task 89): book cycles

Разделение как у книг: `series` — общий каталог циклов, `userseries` — личный
статус читателя. Принадлежность книги циклу (`book.series_id`, `series_index`) —
свойство самой книги.

⚠ Колонки в `book` добавляем ОБЫЧНЫМ add_column, без batch_alter_table:
batch пересоздаёт таблицу через DROP, а при включённом PRAGMA foreign_keys это
каскадом сносит дочерние строки (инцидент миграции 0005 — потеряли атмосферу
у 14 книг). FK для ORM объявлен в models.py; на уровне SQLite ограничимся
индексом — данных это не портит.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-22

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("design", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_series_name", "series", ["name"])

    op.create_table(
        "userseries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="reading"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "series_id", name="uq_userseries_user_series"),
    )
    op.create_index("ix_userseries_user_id", "userseries", ["user_id"])
    op.create_index("ix_userseries_series_id", "userseries", ["series_id"])

    op.add_column("book", sa.Column("series_id", sa.Integer(), nullable=True))
    op.add_column("book", sa.Column("series_index", sa.Integer(), nullable=True))
    op.create_index("ix_book_series_id", "book", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_book_series_id", "book")
    op.drop_column("book", "series_index")
    op.drop_column("book", "series_id")
    op.drop_index("ix_userseries_series_id", "userseries")
    op.drop_index("ix_userseries_user_id", "userseries")
    op.drop_table("userseries")
    op.drop_index("ix_series_name", "series")
    op.drop_table("series")
