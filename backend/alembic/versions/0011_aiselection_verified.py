"""AISelection.verified (task 85): mark music saved during a Spotify ban

False = музыка сохранена без резолва (Spotify был в куладауне): треки не
проверены, плейлиста нет. reverify_music перепроверит, когда Spotify отпустит.
Старые записи считаем проверенными (server_default true).

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-22

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "aiselection",
        sa.Column(
            "verified", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    op.drop_column("aiselection", "verified")
