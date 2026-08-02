"""Разрешение пути к SQLite-файлу (задача 105).

`sqlite:///library.db` — путь относительно ТЕКУЩЕЙ папки. Из-за этого скрипт,
запущенный из `backend/scripts/`, открывал не рабочую базу, а заводил рядом
с собой пустую и печатал «0 записей» вместо того, чтобы упасть. Пустая база
успела уехать даже в Docker-образ.

Здесь проверяется, что относительный путь всегда ведёт в `backend/`,
а всё остальное — абсолютные пути, `:memory:`, Postgres — не тронуто.
"""

from pathlib import Path

from database import BACKEND_DIR, anchor_sqlite_path


def test_relative_path_anchored_to_backend():
    """Главная проверка: cwd больше ни на что не влияет."""
    result = anchor_sqlite_path("sqlite:///library.db")

    assert result == "sqlite:///" + (BACKEND_DIR / "library.db").as_posix()
    assert Path(result[len("sqlite:///"):]).is_absolute()


def test_posix_absolute_path_untouched():
    """На проде путь абсолютный (`sqlite:////data/library.db`, четыре слэша) —
    трогать его нельзя, там volume.

    ⚠ Проверка обязана работать НА WINDOWS тоже. Первая версия использовала
    `Path(...).is_absolute()`, а он платформозависим: на Windows
    `/data/library.db` абсолютным не считается (нет буквы диска), и прод-путь
    локально переписывался в `sqlite:///C:/data/library.db`. Разработка идёт
    на Windows, прод на Linux — строка одна, семантика разная."""
    assert anchor_sqlite_path("sqlite:////data/library.db") == "sqlite:////data/library.db"


def test_windows_absolute_path_untouched():
    """Абсолютный путь Windows тоже не трогаем — на случай своей базы вне репо."""
    assert anchor_sqlite_path("sqlite:///C:/base/library.db") == "sqlite:///C:/base/library.db"
    assert anchor_sqlite_path("sqlite:///D:\\base\\library.db") == "sqlite:///D:\\base\\library.db"


def test_memory_untouched():
    """Тесты гоняются на in-memory базе."""
    assert anchor_sqlite_path("sqlite:///:memory:") == "sqlite:///:memory:"
    assert anchor_sqlite_path("sqlite://") == "sqlite://"


def test_non_sqlite_untouched():
    """Задел под Postgres (з.33) не должен пострадать."""
    dsn = "postgresql+psycopg://user:pass@localhost/nocturne"

    assert anchor_sqlite_path(dsn) == dsn


def test_nested_relative_path_anchored():
    """Путь с подпапкой тоже привязывается к backend/, а не к cwd."""
    result = anchor_sqlite_path("sqlite:///backups/library.db")

    assert result == "sqlite:///" + (BACKEND_DIR / "backups" / "library.db").as_posix()
