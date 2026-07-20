"""Event.detail: строка -> JSON-структура (задача 80)

Тип колонки в SQLite не меняем (JSON там и так хранится в TEXT — SQLAlchemy
сериализует сам), поэтому НЕ пересоздаём таблицу batch'ем — только конвертируем
данные. Старые значения: '' -> {}, валидный JSON-объект остаётся как есть,
любая другая строка (например 'auto' или 'q=...; found=3') -> {"note": строка} —
историю не парсим, но и не теряем.

⚠ Если будущий autogenerate предложит alter_column detail TEXT->JSON —
этот op можно смело удалять: физический тип не меняется.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-20

"""
import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, detail FROM event")).fetchall()
    for row_id, detail in rows:
        old = detail or ""
        try:
            parsed = json.loads(old)
            # объект оставляем; число/список/строка-JSON — оборачиваем
            new = parsed if isinstance(parsed, dict) else {"note": parsed}
        except (TypeError, ValueError):
            new = {"note": old} if old else {}
        conn.execute(
            sa.text("UPDATE event SET detail = :d WHERE id = :i"),
            {"d": json.dumps(new, ensure_ascii=False), "i": row_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, detail FROM event")).fetchall()
    for row_id, detail in rows:
        try:
            parsed = json.loads(detail or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and set(parsed) <= {"note"}:
            new = str(parsed.get("note", ""))
        else:
            new = json.dumps(parsed, ensure_ascii=False)
        conn.execute(
            sa.text("UPDATE event SET detail = :d WHERE id = :i"),
            {"d": new, "i": row_id},
        )
