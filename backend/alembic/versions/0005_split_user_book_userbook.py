"""Split Book into User / Book (shared catalog) / UserBook (personal shelf)

Разделяем смешанную таблицу book на три:
- user        — кто читает (пока один, id=1, admin);
- book         — книго-внутренние поля (общий каталог, атмосфера и плейлист на книге);
- userbook     — личное: статус, оценка, дата прочтения, связь user↔book.

Переносим личные поля каждой книги в userbook (user_id=1), затем убираем их из book.
ВАЖНО: перед прогоном сделать бэкап library.db (python backup_db.py) — миграция
пересоздаёт таблицу book в SQLite (batch mode).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _assert_fk_off() -> None:
    """Предохранитель: пересоздание book в SQLite делает DROP TABLE, а он при
    включённых FK каскадом снёс бы aiselection и userbook. env.py выключает FK
    на время миграции; если по какой-то причине он включён — отказываемся
    выполняться, чтобы не потерять данные (бэкап бэкапом, но лучше не доводить)."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        fk_on = bind.exec_driver_sql("PRAGMA foreign_keys").scalar()
        if fk_on:
            raise RuntimeError(
                "PRAGMA foreign_keys включён — batch DROP TABLE каскадом удалит "
                "aiselection/userbook. Проверь, что env.py выключает FK на миграцию."
            )


def upgrade() -> None:
    _assert_fk_off()
    # 1) Пользователь: единственный, админ (перегенерация/правка книги — под admin)
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute(
        "INSERT INTO user (id, display_name, is_admin, created_at) "
        "VALUES (1, 'Ксения', 1, CURRENT_TIMESTAMP)"
    )

    # 2) Полка пользователя
    op.create_table(
        "userbook",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["book.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "book_id", name="uq_userbook_user_book"),
        sa.CheckConstraint(
            "rating IS NULL OR status = 'read'",
            name="ck_userbook_rating_only_read",
        ),
    )
    op.create_index("ix_userbook_user_id", "userbook", ["user_id"])
    op.create_index("ix_userbook_book_id", "userbook", ["book_id"])

    # 3) Переносим личные поля каждой книги в userbook (до удаления колонок!)
    op.execute(
        "INSERT INTO userbook "
        "(user_id, book_id, status, rating, read_at, created_at, updated_at) "
        "SELECT user_id, id, status, rating, read_at, created_at, "
        "COALESCE(updated_at, created_at) "
        "FROM book"
    )

    # 4) Убираем из book личные поля и переехавший CHECK-constraint.
    #    batch_alter_table пересоздаёт таблицу (SQLite) — как в ревизиях 0003/0004.
    with op.batch_alter_table("book") as batch:
        batch.drop_constraint("ck_book_rating_only_read", type_="check")
        batch.drop_column("user_id")
        batch.drop_column("status")
        batch.drop_column("rating")
        batch.drop_column("read_at")
        batch.drop_column("updated_at")


def downgrade() -> None:
    _assert_fk_off()   # book пересоздаётся дважды — тот же каскадный риск
    # 1) Возвращаем личные колонки в book — сначала NULLABLE: при пересоздании
    #    таблицы (SQLite batch) новые колонки заполняются уже после копирования
    #    строк, поэтому NOT NULL здесь сразу упал бы (book.user_id).
    with op.batch_alter_table("book") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("status", sa.String(), nullable=True))
        batch.add_column(sa.Column("rating", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("read_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    # 2) Заливаем обратно из userbook (берём запись пользователя для книги)
    op.execute(
        "UPDATE book SET "
        "status = (SELECT ub.status FROM userbook ub WHERE ub.book_id = book.id LIMIT 1), "
        "rating = (SELECT ub.rating FROM userbook ub WHERE ub.book_id = book.id LIMIT 1), "
        "read_at = (SELECT ub.read_at FROM userbook ub WHERE ub.book_id = book.id LIMIT 1), "
        "updated_at = (SELECT ub.updated_at FROM userbook ub WHERE ub.book_id = book.id LIMIT 1), "
        "user_id = (SELECT ub.user_id FROM userbook ub WHERE ub.book_id = book.id LIMIT 1)"
    )
    # книги-сироты без записи на полке (теоретически) — разумные значения по умолчанию
    op.execute("UPDATE book SET user_id = 1 WHERE user_id IS NULL")
    op.execute("UPDATE book SET status = 'want' WHERE status IS NULL")
    op.execute("UPDATE book SET updated_at = created_at WHERE updated_at IS NULL")

    # 3) Данные на месте — теперь можно вернуть NOT NULL и CHECK (ещё одно
    #    пересоздание таблицы, но строки уже заполнены)
    with op.batch_alter_table("book") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("status", existing_type=sa.String(), nullable=False)
        batch.create_check_constraint(
            "ck_book_rating_only_read",
            "rating IS NULL OR status = 'read'",
        )

    op.drop_index("ix_userbook_book_id", "userbook")
    op.drop_index("ix_userbook_user_id", "userbook")
    op.drop_table("userbook")
    op.drop_table("user")
