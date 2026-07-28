# Выдать инвайт-код (этап 9): регистрация в сервисе — только по приглашению.
# Запуск из backend/:
#   python scripts/make_invite.py "Аня"        — создать код с пометкой
#   python scripts/make_invite.py --list       — показать выданные и их статус
import os
import secrets
import sys

from sqlmodel import Session, select

import _bootstrap  # noqa: F401  (кладёт backend/ в sys.path)
import database
from models import Invite, User

# Куда звать приглашённого. Локально это Vite (5173), на проде — сам сервис;
# переопределяется переменной окружения SITE_URL.
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")


def create(note: str) -> None:
    # 4 группы по 4 символа: диктовать голосом и вводить руками терпимо
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    with Session(database.engine) as session:
        session.add(Invite(code=code, note=note))
        session.commit()
    print(f"Код: {code}   (кому: {note or '—'})")
    print(f"Ссылка для приглашённого: {SITE_URL}/login")


def show() -> None:
    with Session(database.engine) as session:
        invites = session.exec(select(Invite).order_by(Invite.id)).all()
        users = {u.id: u for u in session.exec(select(User)).all()}
    if not invites:
        print("Кодов пока нет.")
        return
    for i in invites:
        if i.used_by_user_id:
            who = users.get(i.used_by_user_id)
            status = f"использован: {who.email if who else i.used_by_user_id}"
        else:
            status = "свободен"
        print(f"{i.code}  {status:45}  {i.note or ''}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--list":
        show()
    else:
        create(arg)
