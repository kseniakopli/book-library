"""Initial schema: book, aiselection, catalog, event

Стартовая ревизия. Описывает схему, которая исторически создавалась через
create_all + migrate.py (миграции 1-4). Для уже существующей library.db
эту ревизию НЕ применяют, а помечают: alembic stamp head.
Свежая база разворачивается целиком: alembic upgrade head.

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "book",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("cover_url", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("categories", sa.String(), nullable=True),
        sa.Column("published_year", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("external_rating", sa.Float(), nullable=True),
        sa.Column("raw_metadata", sa.String(), nullable=True),
        sa.Column("isbn", sa.String(), nullable=True),
        sa.Column("enrich_status", sa.String(), nullable=False, server_default="ready"),
    )

    op.create_table(
        "aiselection",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["book.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "book_id", "category", "source",
            name="uq_aiselection_book_category_source",
        ),
    )
    op.create_index("ix_aiselection_book_id", "aiselection", ["book_id"])

    op.create_table(
        "catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("cover_url", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_catalog_title", "catalog", ["title"])
    op.create_index("ix_catalog_author", "catalog", ["author"])

    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_event_type", "event", ["type"])
    op.create_index("ix_event_book_id", "event", ["book_id"])


def downgrade() -> None:
    op.drop_table("event")
    op.drop_table("catalog")
    op.drop_table("aiselection")
    op.drop_table("book")
