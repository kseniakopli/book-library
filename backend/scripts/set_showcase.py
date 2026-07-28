# Настроить публичную витрину (задача 30). Запуск из backend/:
#   python scripts/set_showcase.py publiclib "Библиотека" "Подпись под заголовком"
#   python scripts/set_showcase.py --off          — убрать витрину
#   python scripts/set_showcase.py --show         — показать текущие настройки
#
# Слаг задаётся скриптом, а не в интерфейсе: витрина у владельца одна, меняется
# раз в жизни, а UI для этого пришлось бы городить с проверкой занятости.
import re
import sys

from sqlmodel import Session, select

import _bootstrap  # noqa: F401
import database
from models import User, UserBook

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")


def _admin(session: Session) -> User:
    user = session.exec(select(User).where(User.is_admin == True)).first()  # noqa: E712
    if user is None:
        raise SystemExit("Не найден пользователь-админ")
    return user


def show() -> None:
    with Session(database.engine) as session:
        user = _admin(session)
        featured = session.exec(
            select(UserBook).where(
                UserBook.user_id == user.id, UserBook.featured == True  # noqa: E712
            )
        ).all()
    if not user.public_slug:
        print("Витрина не настроена.")
    else:
        print(f"Адрес:     /u/{user.public_slug}")
        print(f"Заголовок: {user.public_title or '(по умолчанию)'}")
        print(f"Подпись:   {user.public_intro or '—'}")
    print(f"Книг в витрине: {len(featured)}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "--show":
        show()
        return

    with Session(database.engine) as session:
        user = _admin(session)
        if args[0] == "--off":
            user.public_slug = None
            print("Витрина выключена — страница отдаёт 404.")
        else:
            slug = args[0].strip().lower()
            if not SLUG_RE.match(slug):
                raise SystemExit(
                    "Слаг: латиница, цифры и дефис, 2–31 символ (например publiclib)"
                )
            user.public_slug = slug
            if len(args) > 1:
                user.public_title = args[1]
            if len(args) > 2:
                user.public_intro = args[2]
            print(f"Витрина: /u/{slug}")
            print("Отметьте книги кнопкой «В витрину» на их страницах.")
        session.add(user)
        session.commit()


if __name__ == "__main__":
    main()
