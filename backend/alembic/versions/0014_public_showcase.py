"""Public showcase (task 30): user.public_slug + userbook.featured

Витрина — не «вся полка», а отобранные книги с готовой атмосферой: это
рекламная страница, на которую ведут QR печатных карточек. Поэтому две вещи:
адрес витрины у пользователя (пусто — витрины нет) и отметка у книги на полке.

⚠ Колонки добавляем ОБЫЧНЫМ add_column, без batch_alter_table: batch пересоздаёт
таблицу через DROP, а при включённом PRAGMA foreign_keys это каскадом сносит
дочерние строки (инцидент миграции 0005).

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-26

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("public_slug", sa.String(), nullable=True))
    op.add_column("user", sa.Column("public_title", sa.String(), nullable=True))
    op.add_column("user", sa.Column("public_intro", sa.String(), nullable=True))
    op.create_index("ix_user_public_slug", "user", ["public_slug"], unique=True)

    op.add_column(
        "userbook",
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("userbook", "featured")
    op.drop_index("ix_user_public_slug", table_name="user")
    op.drop_column("user", "public_intro")
    op.drop_column("user", "public_title")
    op.drop_column("user", "public_slug")
