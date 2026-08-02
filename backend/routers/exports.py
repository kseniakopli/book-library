# Экспорт полки (задачи 35 и 42). HTTP-слой тонкий: сборка файла —
# в services/export.py.
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session

from constants import EVENT_EXPORT
from deps import current_user_id, get_session
from events import log_event
from services.export import export_filename, shelf_to_csv

router = APIRouter(tags=["export"])


@router.get("/export/shelf.csv")
def export_shelf_csv(
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
):
    """Своя полка одним CSV-файлом.

    Личное действие, не admin: выгружается ТОЛЬКО полка вызывающего
    (`UserBook.user_id == user_id`), общий каталог как таковой не отдаётся.

    Отдаём файл целиком, а не потоком: библиотека персональная (сотни книг,
    десятки килобайт), а StreamingResponse усложнил бы обработку ошибок —
    исключение посреди потока клиент получил бы как оборванный файл с кодом
    200. Появятся тысячи книг — переделать.
    """
    body = shelf_to_csv(session, user_id)
    filename = export_filename()
    log_event(EVENT_EXPORT, detail={"format": "csv", "bytes": len(body)})
    return Response(
        # кодировка utf-8-sig: BOM уже внутри строки (см. services/export.py),
        # поэтому кодируем обычным utf-8, иначе BOM удвоится
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
