import requests


# --- Обогащение: тянем обложку и описание из Google Books ---
def fetch_book_info(title: str, author: str, lang: str = "ru") -> dict:
    """Спрашиваем у Google Books обложку и описание.
    Возвращаем словарь {cover_url, description}. Если что-то не нашлось
    или сервис недоступен — возвращаем None, книга всё равно сохранится."""
    result = {"cover_url": None, "description": None}
    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": f"intitle:{title}+inauthor:{author}",
                "maxResults": 1,
                "langRestrict": lang,        # язык, на котором хотим описание
            },
            timeout=5,                      # не ждём ответа дольше 5 секунд
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return result
        info = items[0].get("volumeInfo", {})
        result["description"] = info.get("description")
        image_links = info.get("imageLinks", {})
        cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover:
            result["cover_url"] = cover.replace("http://", "https://")
    except requests.RequestException:
        pass
    return result