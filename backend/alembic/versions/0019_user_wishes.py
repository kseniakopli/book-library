"""User.wishes (з.114, 03.08): пожелания читателя для рекомендаций

Свободный текст вроде «не люблю антиутопии, не предлагай». Тот же механизм,
что профиль вкуса по 👍/👎 (з.26 ч.4), только вход не кнопками, а словами:
у моделей нет памяти, поэтому «память» о вкусе живёт у нас и подкладывается
в промпт следующей генерации.

⚠ Текст УЕЗЖАЕТ В ПРОМПТ, поэтому длина ограничена и на уровне схемы
(валидация в роутере), и здесь размером поля не ограничивается специально:
SQLite всё равно хранит TEXT, а настоящая защита — проверка на входе.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-03

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("wishes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "wishes")
