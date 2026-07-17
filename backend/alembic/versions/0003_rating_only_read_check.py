"""CHECK: rating only for status='read' (task 7)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-16

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Страховка: чистим возможные нарушения ДО включения constraint,
    # иначе пересоздание таблицы (SQLite batch) упадёт на переносе данных
    op.execute(
        "UPDATE book SET rating = NULL "
        "WHERE status != 'read' AND rating IS NOT NULL"
    )
    with op.batch_alter_table("book") as batch:
        batch.create_check_constraint(
            "ck_book_rating_only_read",
            "rating IS NULL OR status = 'read'",
        )


def downgrade() -> None:
    with op.batch_alter_table("book") as batch:
        batch.drop_constraint("ck_book_rating_only_read", type_="check")
