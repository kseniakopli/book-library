# Рекомендации новых книг (этап 8).
# Генерируются ПО КНОПКЕ (решение 19.07): LLM смотрит на высоко оценённые книги
# и предлагает те, которых в библиотеке нет. Набор хранится в БД и заменяется
# целиком при следующей генерации — на главной он просто читается.
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

import database
from constants import (
    EVENT_AI_RECOMMENDATIONS,
    SOURCE_CHATGPT,
    SOURCE_CLAUDE,
    STATUS_READ,
)
from deps import current_user_id, get_lang, get_session
from events import log_event
from google_books import search_books
from models import Author, Book, BookAuthor, Genre, Recommendation, User, UserBook
from services.ai import generate_recommendations, start_ai_metrics, take_ai_metrics
from services.ai_schemas import RecommendationsResult
from services.authors import norm_key
from services.taste import disliked_recommendations

router = APIRouter(tags=["recommendations"])


MIN_RATING = 7        # «понравилось» — сильный сигнал
# Задача 124: 5–6 это НЕ «понравилось послабее», а другой род чтения —
# одноразовое, для расслабления (детективы, фэнтези). Такие книги тоже
# хочется получать в советах, но подавать их надо отдельным списком:
# смешав, мы скажем модели, что оценка 5 значит «нравится».
CASUAL_MIN = 5
MAX_FAVORITES = 20    # столько любимых книг отдаём модели (промпт не резиновый)
MAX_CASUAL = 10       # «для отдыха» — вдвое меньше: это фон, а не основа
COUNT = 5             # столько советов просим У КАЖДОЙ модели (итого до 10)
MAX_GENRE_PICKS = 15  # больше — это уже не выбор, а весь справочник


# ⚠ Константы объявлены ВЫШЕ класса: тело класса выполняется при импорте,
# и `Field(max_length=MAX_GENRE_PICKS)` вычисляется прямо там.
class SettingsIn(BaseModel):
    """Настройки рекомендаций (задача 124).

    Пришли на смену пожеланиям словами (з.114): свободный текст было
    непонятно, как исполнять, и проверить его исполнение нечем.

    ⚠ Жанры приходят списком `slug`, а не id: жанр без книг удаляется
    (`services/genres._drop_orphans`), и сохранённый id протух бы молча.
    Длина ограничена — список уезжает в промпт.
    """
    skip_known_authors: bool = False
    genres_include: list[str] = Field(default_factory=list, max_length=MAX_GENRE_PICKS)
    genres_exclude: list[str] = Field(default_factory=list, max_length=MAX_GENRE_PICKS)


def _norm(title: str, author: str) -> tuple[str, str]:
    return title.strip().lower(), author.strip().lower()


def _stored(session: Session, user_id: int) -> dict:
    """Сохранённые рекомендации пользователя в формате ответа."""
    rows = session.exec(
        select(Recommendation)
        .where(Recommendation.user_id == user_id)
        .order_by(Recommendation.id)
    ).all()
    return {
        "recommendations": [
            {
                "title": r.title,
                "author": r.author,
                "reason": r.reason,
                "source": r.source,
                "cover_url": r.cover_url,
                "external_id": r.external_id,
            }
            for r in rows
        ]
    }


@router.get("/recommendations")
def list_recommendations(
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
):
    """Сохранённые рекомендации (пусто — фронт зовёт подобрать).

    Вместе с ними — настройки и справочник жанров (з.124): страница
    показывает их рядом с кнопкой, и три запроса ради одного экрана
    были бы лишними.
    """
    user = session.get(User, user_id)
    return {
        **_stored(session, user_id),
        "settings": _settings_of(user),
        # варианты для выбора — только жанры, У КОТОРЫХ ЕСТЬ КНИГИ:
        # пустой жанр в справочнике не живёт (`_drop_orphans`), но список
        # строим тем же запросом, что и страница жанров, чтобы порядок совпал
        "genres": [
            {"slug": g.slug, "name": g.name}
            for g in session.exec(select(Genre).order_by(Genre.slug)).all()
        ],
    }


def _settings_of(user: User | None) -> dict:
    """Настройки в формате ответа. Пустая строка и None — это «ничего
    не выбрано», поэтому разбор одинаков для обоих случаев."""
    if user is None:
        return {"skip_known_authors": False, "genres_include": [], "genres_exclude": []}
    split = lambda raw: [s for s in (raw or "").split(",") if s]   # noqa: E731
    return {
        "skip_known_authors": user.rec_skip_known_authors,
        "genres_include": split(user.rec_genres_include),
        "genres_exclude": split(user.rec_genres_exclude),
    }


@router.put("/recommendations/settings")
def save_settings(
    data: SettingsIn,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
):
    """Сохранить настройки подбора (задача 124).

    ЛИЧНОЕ действие: настройки влияют только на свои советы, поэтому без
    admin-гейта — то же основание, что было у пожеланий словами.

    ⚠ Сохраняем только жанры, которые ЕСТЬ в справочнике: список приходит
    с клиента, и принимать на веру произвольные строки, которые потом уедут
    в промпт, незачем. Неизвестное молча отбрасывается — это не ошибка
    пользователя, а разошедшееся состояние (жанр могли удалить, пока
    страница была открыта).
    """
    known = {g.slug for g in session.exec(select(Genre)).all()}
    keep = lambda picks: ",".join(s for s in dict.fromkeys(picks) if s in known)  # noqa: E731

    user = session.get(User, user_id)
    user.rec_skip_known_authors = data.skip_known_authors
    user.rec_genres_include = keep(data.genres_include) or None
    user.rec_genres_exclude = keep(data.genres_exclude) or None
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"settings": _settings_of(user)}


@router.post("/recommendations")
async def generate(lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Подобрать рекомендации заново — по кнопке (тратит токены).

    Этап 9: доступно КАЖДОМУ вошедшему. Набор рекомендаций личный
    (`Recommendation.user_id`) и строится по своим оценкам — админ тут ни при
    чём. Расходы держат лимиты частоты и капы у провайдеров (з.36).
    Сессию открываем вручную КОРОТКИМИ отрезками (не через get_session):
    между ними идёт долгий AI-вызов, держать соединение всё это время не нужно."""
    with Session(database.engine) as session:

        # 1) сигналы. Задача 124: ДВА списка, а не один.
        #    7–10 — «люблю такое», 5–6 — «читалось для отдыха». Это разные
        #    поводы советовать, и модель должна видеть разницу: одним списком
        #    оценка 5 читалась бы как «понравилось».
        def rated(low: int, high: int, limit: int) -> list[str]:
            rows = session.exec(
                select(Book, UserBook)
                .join(UserBook, UserBook.book_id == Book.id)
                .where(
                    UserBook.user_id == user_id,
                    UserBook.status == STATUS_READ,
                    UserBook.rating.is_not(None),
                    UserBook.rating >= low,
                    UserBook.rating <= high,
                )
                .order_by(UserBook.rating.desc(), UserBook.read_at.desc())
                .limit(limit)
            ).all()
            return [f"{b.title} — {b.author} ({ub.rating}/10)" for b, ub in rows]

        favorites = rated(MIN_RATING, 10, MAX_FAVORITES)
        casual = rated(CASUAL_MIN, MIN_RATING - 1, MAX_CASUAL)

        # 2) что уже есть на полке — не предлагать повторно
        shelf = session.exec(
            select(Book.title, Book.author)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == user_id)
        ).all()
        exclude = [f"{t} — {a}" for t, a in shelf]
        known = {_norm(t, a) for t, a in shelf}
        # задача 26 ч.4: советы, помеченные 👎 — «такое не заходит»
        disliked = disliked_recommendations(session, user_id)

        # --- задача 124: настройки подбора ---
        user = session.get(User, user_id)
        settings = _settings_of(user)
        names = {g.slug: g.name for g in session.exec(select(Genre)).all()}
        # в промпт уезжают ИМЕНА, а не slug: модель читает по-человечески
        genres_include = [names[s] for s in settings["genres_include"] if s in names]
        genres_exclude = [names[s] for s in settings["genres_exclude"] if s in names]

        # Авторы, которые уже есть на полке. Берём сущности, а не строку
        # `book.author`: у книги может быть несколько авторов, и написание
        # в строке бывает как в источнике («Ann Patchett»), а имя из сущности
        # русское — модели полезнее второе.
        skip_authors: list[str] = []
        skip_keys: set[str] = set()
        if settings["skip_known_authors"]:
            rows = session.exec(
                select(Author)
                .join(BookAuthor, BookAuthor.author_id == Author.id)
                .join(UserBook, UserBook.book_id == BookAuthor.book_id)
                .where(UserBook.user_id == user_id)
                .distinct()
            ).all()
            for author in rows:
                skip_authors.append(author.name_ru or author.name_original or "")
                skip_keys.add(author.sort_key)
            skip_authors = sorted({a for a in skip_authors if a})

    if not favorites and not casual:
        # нечего анализировать — честно говорим, токены не тратим
        return {"recommendations": [], "detail": "no_favorites"}

    start_ai_metrics()   # задача 80: латентность и токены — в событие
    # 20.07: спрашиваем ОБЕ модели, по COUNT советов у каждой
    # 22.07: + disliked — обратная петля фидбека (з.26 ч.4)
    results = await generate_recommendations(
        favorites, exclude, COUNT, lang, disliked,
        casual=casual,
        skip_authors=skip_authors,
        genres_include=genres_include,
        genres_exclude=genres_exclude,
    )

    # 3) дедуп: (а) книги с полки — модель могла не заметить список исключений;
    #    (б) советы, совпавшие у обеих моделей — показываем один раз.
    #    Источники перебираем в фиксированном порядке, чтобы у одинакового
    #    набора был предсказуемый результат, а не «кто раньше ответил».
    #    (в) задача 124: авторы с полки, если чекбокс включён. Список ушёл
    #        и в промпт, но просьба — не гарантия: имена мы знаем, значит
    #        проверяем кодом, а не надеемся (Уроки 1.1). Сверяем по тому же
    #        ключу, что и таблица авторов, — иначе «Кинг, Стивен» и
    #        «Стивен Кинг» разошлись бы.
    fresh = []          # [(источник, item)]
    seen = set()
    dropped_authors = 0
    for source in (SOURCE_CLAUDE, SOURCE_CHATGPT):
        for item in results.get(source, RecommendationsResult(items=[])).items:
            key = _norm(item.title, item.author)
            if key in known or key in seen:
                continue
            if skip_keys and norm_key(item.author) in skip_keys:
                dropped_authors += 1
                continue
            seen.add(key)
            fresh.append((source, item))

    # 4) обложки: один поиск в Google Books на книгу (мягко — без обложки тоже ок)
    covers = {}
    for _, item in fresh:
        candidates = search_books(f"{item.title} {item.author}", max_results=3)
        match = next((c for c in candidates if c.get("cover_url")), None)
        if match:
            covers[_norm(item.title, item.author)] = match

    # 5) заменяем набор целиком
    with Session(database.engine) as session:
        for old in session.exec(
            select(Recommendation).where(Recommendation.user_id == user_id)
        ).all():
            session.delete(old)
        session.flush()
        for source, item in fresh:
            found = covers.get(_norm(item.title, item.author)) or {}
            session.add(Recommendation(
                user_id=user_id,
                title=item.title,
                author=item.author,
                reason=item.reason,
                source=source,
                cover_url=found.get("cover_url"),
                external_id=found.get("external_id"),
                created_at=datetime.now(),
            ))
        session.commit()

    by_source = {
        source: sum(1 for s, _ in fresh if s == source)
        for source in (SOURCE_CLAUDE, SOURCE_CHATGPT)
    }
    log_event(EVENT_AI_RECOMMENDATIONS, detail={
        "count": len(fresh), "by_source": by_source, "ai_calls": take_ai_metrics(),
        # задача 124: сколько советов пришлось отсеять по авторам. Это мера
        # того, насколько модель слушается просьбы: растёт — значит просьба
        # в промпте не работает и надо менять формулировку, а не фильтр.
        "dropped_known_authors": dropped_authors,
    })
    with Session(database.engine) as session:
        return _stored(session, user_id)
