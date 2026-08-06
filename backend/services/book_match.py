"""Существует ли книга, которую посоветовала модель (задача 126, 06.08).

Зачем. 06.08 в рекомендациях приехала книга «И как только мы вернёмся»
некой Бенедетты Кристофани — её нет нигде. Модель не врала намеренно:
у неё нет способа отличить книгу, которую она «помнит», от книги, которую
она только что составила из правдоподобных частей. Отличить может внешний
каталог — ровно так же, как Spotify отличает выдуманный трек (инцидент
20.07, `services/track_match.py`).

⚠ Запрос к Google Books на каждый совет мы УЖЕ делали — ради обложки.
Ответ «ничего похожего» просто не использовался, хотя именно у выдуманных
книг обложки и не было. Здесь этот ответ наконец читается.

Только ЧИСТЫЕ функции: ни сети, ни базы. Кандидатов приносит вызывающий.
"""

import re

from services.text_match import similarity

# Пороги. Ниже, чем у треков (0.72/0.6): у книги название переводят
# и сокращают чаще, чем у песни, а цена ошибки здесь несимметрична —
# лучше показать настоящую книгу с неидеальным совпадением, чем выбросить
# её как выдумку. Число отсеянных пишется в событие: поедет вверх —
# пороги пересмотрим по фактам, а не по ощущению.
TITLE_RATIO = 0.70
AUTHOR_RATIO = 0.55
# Кандидат без указанного автора: сверять не с чем, поэтому от названия
# требуем почти точного совпадения.
TITLE_RATIO_NO_AUTHOR = 0.90


def normalize_title(value: str) -> str:
    """Название книги к сравнимому виду.

    ⚠ Отличается от нормализации треков: там мешают «- Remastered 2011»
    и «(feat. X)», здесь — подзаголовок после двоеточия («Щегол: роман»)
    и пометки в скобках («Убежище 3/9 (сборник)»). Отсюда и отдельный
    модуль, а не общая функция на оба случая.
    """
    text = (value or "").lower().replace("ё", "е")
    text = re.split(r"\s*[:(\[]", text)[0]          # подзаголовок и скобки
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def normalize_author(value: str) -> str:
    """Имя автора к сравнимому виду.

    Google Books отдаёт авторов списком через запятую, а модель — строкой;
    инициалы и порядок «Фамилия, Имя» встречаются в обоих. Поэтому имя
    разбирается на слова и сортируется: «Тана Френч» и «Френч, Тана»
    становятся одинаковыми.
    """
    text = (value or "").lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(sorted(text.split()))


def find_match(candidates: list[dict], title: str, author: str) -> dict | None:
    """Кандидат из Google Books, который ДЕЙСТВИТЕЛЬНО является этой книгой.

    Возвращает лучшего подходящего или None, если совпадений нет —
    это и означает «книга не подтвердилась».

    ⚠ Берём не первого попавшегося, а лучшего по сумме похожестей: поиск
    по «название + автор» часто возвращает сначала книги О книге
    (исследования, путеводители), и первый результат бывает не тем.
    Ровно эта ошибка была в Spotify 20.07 и до 06.08 жила здесь —
    обложка бралась у первого кандидата, у которого она вообще есть.
    """
    want_title = normalize_title(title)
    want_author = normalize_author(author)
    if not want_title:
        return None

    best, best_score = None, 0.0
    for candidate in candidates:
        title_score = similarity(want_title, normalize_title(candidate.get("title", "")))

        raw_author = candidate.get("author") or ""
        # «—» ставит наш же google_books.py, когда авторов у тома нет
        if raw_author and raw_author != "—":
            if title_score < TITLE_RATIO:
                continue
            author_score = similarity(want_author, normalize_author(raw_author))
            if author_score < AUTHOR_RATIO:
                continue
        else:
            if title_score < TITLE_RATIO_NO_AUTHOR:
                continue
            author_score = 0.0

        score = title_score + author_score
        if score > best_score:
            best, best_score = candidate, score

    return best
