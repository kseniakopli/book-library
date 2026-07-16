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
    "import_too_large":     {"ru": "Файл слишком большой (лимит 2 МБ)",
                             "en": "File is too large (2 MB limit)"},
    "import_bad_encoding":  {"ru": "Файл должен быть в кодировке UTF-8",
                             "en": "File must be UTF-8 encoded"},
    "import_too_many_rows": {"ru": "Слишком много строк (лимит 2000)",
                             "en": "Too many rows (2000 limit)"},
    "bad_category":         {"ru": "Неизвестная категория атмосферы",
                             "en": "Unknown atmosphere category"},
    "no_music_for_playlist": {"ru": "Сначала подберите музыку — плейлист собирается из неё",
                              "en": "Generate music first — the playlist is built from it"},
    "no_playlist_for_qr":   {"ru": "Сначала создайте Spotify-плейлист — QR кодирует его ссылку",
                             "en": "Create the Spotify playlist first — the QR encodes its link"},
}


def msg(key: str, lang: str) -> str:
    """Возвращает текст сообщения на нужном языке.
    Если язык незнакомый — откатываемся на русский, чтобы не упасть."""
    translations = MESSAGES[key]
    return translations.get(lang, translations["ru"])