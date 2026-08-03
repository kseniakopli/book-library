# Админский раздел «Заполнение данных» (задача 113).
#
# Только admin: это цифры и списки по ОБЩЕМУ каталогу, а не по чьей-то полке.
# Обычному читателю они ничего не говорят, а ссылки ведут на правку общих
# данных, которая ему всё равно запрещена.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session

from deps import current_user_id, get_lang, get_session, require_admin
from services.atmosphere import generate_design_in_background
from services.data_gaps import ALL_GAPS, PAGE_SIZE, items, summary

router = APIRouter(tags=["admin"])

# Сколько паспортов догенерировать за одно нажатие. Каждый — вызов Claude,
# поэтому партия маленькая и запускается осознанно: у Ксении 189 книг без
# паспорта, и «догенерировать всё» одной кнопкой означало бы 189 запросов
# без возможности передумать.
DESIGN_BATCH = 10


@router.get("/admin/data-gaps")
def read_summary(
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Сколько в каталоге незаполненного. Сначала цифры — от них зависит,
    ручная это работа или нужен ещё один источник данных."""
    require_admin(session, lang, user_id)
    return summary(session)


@router.get("/admin/data-gaps/{kind}")
def read_items(
    kind: str,
    limit: int = Query(default=PAGE_SIZE, le=200),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Конкретные объекты с пробелом — со ссылками на правку."""
    require_admin(session, lang, user_id)
    if kind not in ALL_GAPS:
        raise HTTPException(status_code=404, detail="Неизвестный вид данных")
    return {"kind": kind, "items": items(session, kind, limit)}


@router.post("/admin/backfill-design")
def backfill_design(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=DESIGN_BATCH, le=DESIGN_BATCH),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Задача 116: догенерировать паспорта книгам, у которых их нет.

    Дыра нашлась 02.08 при разборе жалобы тестировщика: `routers/imports.py`
    создаёт `Book` напрямую и НЕ зовёт фоновую генерацию оформления — в отличие
    от добавления по одной. У владельца это незаметно (паспорта добраны
    скриптом), а новый пользователь после импорта своей библиотеки получал
    полку серых заглушек.

    ⚠ Партиями по {DESIGN_BATCH}, а не «всё сразу»: каждый паспорт — вызов
    Claude. Автоматически при импорте не генерируем вовсе — сотня книг
    означала бы сотню запросов на одно нажатие «Импорт CSV».

    Идемпотентно: `generate_design_in_background` сам выходит, если паспорт
    уже есть, поэтому повторное нажатие не тратит токены впустую.
    """
    require_admin(session, lang, user_id)

    without_design = items(session, "no_design", limit)
    for book in without_design:
        background_tasks.add_task(
            generate_design_in_background, book["id"], lang, user_id
        )

    remaining = summary(session)["books"]["no_design"] - len(without_design)
    return {"scheduled": len(without_design), "remaining": max(remaining, 0)}
