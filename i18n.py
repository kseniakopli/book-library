ALLOWED_LANGS = {"ru", "en"}

# --- Тексты сообщений на двух языках ---
MESSAGES = {
    "bad_lang":          {"ru": "lang должен быть ru или en",
                          "en": "lang must be ru or en"},
    "book_not_found":    {"ru": "Книга не найдена",
                          "en": "Book not found"},
    "bad_status":        {"ru": "Статус должен быть want, reading или read",
                          "en": "Status must be want, reading or read"},
    "bad_rating":        {"ru": "Оценка должна быть от 1 до 10",
                          "en": "Rating must be between 1 and 10"},
    "rating_needs_read": {"ru": "Оценку можно ставить только книге со статусом read",
                          "en": "Rating is only allowed for books with status 'read'"},
}


def msg(key: str, lang: str) -> str:
    """Возвращает текст сообщения на нужном языке.
    Если язык незнакомый — откатываемся на русский, чтобы не упасть."""
    translations = MESSAGES[key]
    return translations.get(lang, translations["ru"])