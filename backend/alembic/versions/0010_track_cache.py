"""TrackCache table (task 82 part 1): cache Spotify track resolution

Каждый трек резолвится один раз на всю систему — экономит квоту Spotify
(она на приложение). Кэшируем и положительный, и отрицательный результат.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-22

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trackcache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_key", sa.String(), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("artist", sa.String(), nullable=True),
        sa.Column("uri", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_trackcache_query_key", "trackcache", ["query_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_trackcache_query_key", "trackcache")
    op.drop_table("trackcache")
