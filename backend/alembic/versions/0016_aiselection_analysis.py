"""AISelection.analysis (з.99, 02.08): сохранять рассуждение модели

Приём reasoning-as-schema заставляет модель заполнить поле-анализ ДО ответа
(интонация, кухня, свежие исполнители). Само рассуждение при этом нигде
не сохранялось: в payload уезжали только songs/items. Значит проверить,
сработал ли приём, было нельзя даже постфактум — мы видели результат и
не видели рассуждения, которое к нему привело. Для механизма, вся суть
которого в принуждении к рассуждению, это слепая зона.

Пустая строка у старых записей — анализа для них просто нет.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-02

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "aiselection",
        sa.Column("analysis", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("aiselection", "analysis")
