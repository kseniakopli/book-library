"""Author.bio (з.111, 03.08): биография автора

Заполняется ВРУЧНУЮ (решение Ксении): AI-черновик не берём — биография
живого человека это факты, а не атмосфера, и выдуманная дата рождения
в справочнике хуже, чем пустое поле.

Пусто у всех существующих авторов — писать их будем по одному, глазами.
Поэтому nullable, а не пустая строка: NULL здесь честно значит «ещё
не заполняли», и по нему же считается список незаполненного в з.113.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-03

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("author", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("author", "bio")
