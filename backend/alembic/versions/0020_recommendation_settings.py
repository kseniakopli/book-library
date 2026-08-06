"""Настройки рекомендаций (з.124, 06.08)

Пожелания словами (з.114) заменяются явными настройками: их понятно, как
исполнять, и часть из них можно проверить кодом, а не просить у модели.

- `rec_skip_known_authors` — не советовать авторов, которые уже есть
  на полке. Довод Ксении: про знакомого автора она сама знает, что хочет
  у него дальше, а рекомендация нужна, чтобы открыть нового.
- `rec_genres_include` / `rec_genres_exclude` — списки жанров из справочника
  `Genre`. Хранятся строкой из `slug` через запятую, а НЕ по id: жанр
  без книг удаляется (`_drop_orphans` в `services/genres.py`), и ссылка
  по id протухла бы молча. По `slug` максимум ничего не найдётся, что
  безопасно и читаемо глазами прямо в базе.

⚠ Колонка `wishes` НЕ удаляется этой миграцией, хотя фича снята
с интерфейса: убирать данные в том же заходе необратимо. Уборка — з.125.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-06

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default для существующих строк: без него у заведённых ранее
    # пользователей окажется NULL, а код ждёт булево значение
    op.add_column(
        "user",
        sa.Column(
            "rec_skip_known_authors",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("user", sa.Column("rec_genres_include", sa.Text(), nullable=True))
    op.add_column("user", sa.Column("rec_genres_exclude", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "rec_genres_exclude")
    op.drop_column("user", "rec_genres_include")
    op.drop_column("user", "rec_skip_known_authors")
