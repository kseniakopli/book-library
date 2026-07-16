"""Add book.spotify_playlist_url (stage 10.2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "book", sa.Column("spotify_playlist_url", sa.String(), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("book") as batch:
        batch.drop_column("spotify_playlist_url")
