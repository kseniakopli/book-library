"""Жанры как сущность (з.112, 03.08): genre + bookgenre

⚠ Жанры заводятся ВРУЧНУЮ. Google Books отдаёт «Fiction / General» —
это шум, а не жанры, и агрегировать из него нечего (в отличие от авторов,
где строка книги была настоящим источником). Поэтому таблицы создаются
ПУСТЫМИ: заполняет админ, по одной книге.

Связь многие-ко-многим — решение Ксении: «Демон из Пустоши» это и фэнтези,
и детектив.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-03

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genre",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        # ключ тождества: «Тёмное фэнтези» и «тёмное фэнтези» — один жанр
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_genre_slug", "genre", ["slug"], unique=True)

    op.create_table(
        "bookgenre",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("book.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "genre_id",
            sa.Integer(),
            sa.ForeignKey("genre.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("book_id", "genre_id", name="uq_bookgenre_book_genre"),
    )
    op.create_index("ix_bookgenre_book_id", "bookgenre", ["book_id"])
    op.create_index("ix_bookgenre_genre_id", "bookgenre", ["genre_id"])


def downgrade() -> None:
    op.drop_index("ix_bookgenre_genre_id", table_name="bookgenre")
    op.drop_index("ix_bookgenre_book_id", table_name="bookgenre")
    op.drop_table("bookgenre")
    op.drop_index("ix_genre_slug", table_name="genre")
    op.drop_table("genre")
