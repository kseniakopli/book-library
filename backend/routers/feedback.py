# Обратная связь по AI-подборкам (задача 26): 👍/👎 на атмосферу и рекомендации.
# HTTP-слой тонкий; храним в таблице Feedback (см. models.py).
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from deps import CURRENT_USER_ID, get_session
from models import Feedback

router = APIRouter(tags=["feedback"])

VERDICTS = {"up", "down"}


class FeedbackIn(BaseModel):
    ref: str                      # ключ цели: "atmosphere:5:music:Claude" и т.п.
    verdict: str                  # "up" / "down"
    source: str | None = None     # Claude / ChatGPT — для сводки по провайдерам


@router.get("/feedback")
def list_feedback(session: Session = Depends(get_session)):
    """Все оценки пользователя как {ref: verdict} — фронт рисует состояние кнопок
    одним запросом, не спрашивая по каждой подборке отдельно."""
    rows = session.exec(
        select(Feedback).where(Feedback.user_id == CURRENT_USER_ID)
    ).all()
    return {"feedback": {row.ref: row.verdict for row in rows}}


@router.post("/feedback")
def set_feedback(data: FeedbackIn, session: Session = Depends(get_session)):
    """Поставить/сменить/снять оценку. Повторный тот же вердикт = снять (toggle):
    два состояния кнопки 👍 — включена и выключена. Возвращает актуальный вердикт
    (или null, если сняли)."""
    if data.verdict not in VERDICTS:
        # мягко игнорируем мусор, не роняя фронт
        return {"ref": data.ref, "verdict": None}

    row = session.exec(
        select(Feedback).where(
            Feedback.user_id == CURRENT_USER_ID, Feedback.ref == data.ref
        )
    ).first()

    if row is None:
        session.add(Feedback(
            user_id=CURRENT_USER_ID, ref=data.ref,
            source=data.source, verdict=data.verdict,
        ))
        session.commit()
        return {"ref": data.ref, "verdict": data.verdict}

    if row.verdict == data.verdict:
        session.delete(row)               # тот же вердикт повторно → снять
        session.commit()
        return {"ref": data.ref, "verdict": None}

    row.verdict = data.verdict            # 👍 ↔ 👎
    row.source = data.source or row.source
    session.add(row)
    session.commit()
    return {"ref": data.ref, "verdict": data.verdict}


@router.get("/feedback/summary")
def feedback_summary(session: Session = Depends(get_session)):
    """Acceptance rate по провайдерам: сколько 👍/👎 у Claude и у ChatGPT.
    Считаем только записи с известным source (у атмосферы и рекомендаций он есть)."""
    rows = session.exec(
        select(Feedback).where(
            Feedback.user_id == CURRENT_USER_ID, Feedback.source.is_not(None)
        )
    ).all()
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = summary.setdefault(row.source, {"up": 0, "down": 0})
        if row.verdict in bucket:
            bucket[row.verdict] += 1
    return {"summary": summary}
