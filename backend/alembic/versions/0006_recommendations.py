"""Recommendations table (stage 8)

Рекомендации новых книг: генерируются по кнопке (LLM по высоко оценённым
книгам пользователя) и хранятся до следующей генерации. FK на book нет —
рекомендованной книги в каталоге может не быть.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("cover_url", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )
    op.create_index("ix_recommendation_user_id", "recommendation", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_user_id", "recommendation")
    op.drop_table("recommendation")
