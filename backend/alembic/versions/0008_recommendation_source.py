"""Recommendation.source: кто посоветовал книгу (Claude / ChatGPT)

Советы теперь просим у обеих моделей (20.07), как в атмосфере. У старых записей
источник неизвестен — проставляем Claude, единственный источник до этого.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-20

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendation",
        sa.Column("source", sa.String(), nullable=False, server_default="Claude"),
    )


def downgrade() -> None:
    op.drop_column("recommendation", "source")
