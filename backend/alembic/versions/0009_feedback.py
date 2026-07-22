"""Feedback table (task 26): 👍/👎 on AI picks

Хранит реакцию пользователя на подборки атмосферы и рекомендации — для сводки
Claude vs ChatGPT и будущего «профиля вкуса» в промптах.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-22

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.UniqueConstraint("user_id", "ref", name="uq_feedback_user_ref"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_ref", "feedback", ["ref"])


def downgrade() -> None:
    op.drop_index("ix_feedback_ref", "feedback")
    op.drop_index("ix_feedback_user_id", "feedback")
    op.drop_table("feedback")
