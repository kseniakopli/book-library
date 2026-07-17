"""Add book.read_at and book.updated_at (task 1)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("book", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("book", sa.Column("read_at", sa.DateTime(), nullable=True))
    # для старых книг лучшая оценка updated_at — момент создания;
    # read_at оставляем пустым (реальная дата неизвестна)
    op.execute("UPDATE book SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("book") as batch:
        batch.drop_column("read_at")
        batch.drop_column("updated_at")
