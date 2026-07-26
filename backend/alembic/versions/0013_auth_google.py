"""Auth via Google (stage 9): user identity fields + invite codes

Пароли не заводим — аутентификацию выполняет Google, у нас хранится только его
идентификатор аккаунта (`google_sub`) и почта. Регистрация — по инвайт-коду
(таблица `invite`), потому что каждый новый пользователь тратит платные AI-вызовы.

⚠ Колонки в `user` добавляем ОБЫЧНЫМ add_column, без batch_alter_table:
batch пересоздаёт таблицу через DROP, а при включённом PRAGMA foreign_keys это
каскадом сносит дочерние строки (инцидент миграции 0005 — потеряли атмосферу
у 14 книг; на `user` каскад снёс бы вообще всё).

Существующая строка пользователя (id=1) получает NULL в новых полях и
привязывается к Google-аккаунту при первом входе — см. ADMIN_EMAIL
в services/auth.py.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-24

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("email", sa.String(), nullable=True))
    op.add_column("user", sa.Column("google_sub", sa.String(), nullable=True))
    op.add_column("user", sa.Column("avatar_url", sa.String(), nullable=True))
    op.create_index("ix_user_email", "user", ["email"])
    op.create_index("ix_user_google_sub", "user", ["google_sub"])

    op.create_table(
        "invite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["user.id"]),
    )
    op.create_index("ix_invite_code", "invite", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invite_code", table_name="invite")
    op.drop_table("invite")
    op.drop_index("ix_user_google_sub", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_column("user", "avatar_url")
    op.drop_column("user", "google_sub")
    op.drop_column("user", "email")
