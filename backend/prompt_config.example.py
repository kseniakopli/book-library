# Шаблон промптов сервиса.
# Скопируйте этот файл в prompt_config.py и напишите свои формулировки.
# Реальный prompt_config.py в git НЕ попадает (см. .gitignore) —
# так уникальные промпты остаются приватными.


def build_music_prompt(title: str, author: str, lang: str = "ru") -> str:
    language = "русском" if lang == "ru" else "английском"
    return f"""Ты — музыкальный куратор. Подбери 12 реальных существующих песен
к книге «{title}» ({author}). Пояснение напиши на {language} языке.
"""


def build_design_prompt(title: str, author: str, lang: str = "ru") -> str:
    language = "русском" if lang == "ru" else "английском"
    return f"""Собери «паспорт атмосферы» для оформления карточки книги
«{title}» ({author}). 
Дополнительно нарисуй symbol_svg — минималистичный векторный символ-экслибрис книги:
один элемент <svg viewBox="0 0 100 100"> с простыми формами (path, circle, rect, line),
цвета только из палитры паспорта, без текста, без script/обработчиков/внешних ссылок
и без атрибута href."""

def build_food_prompt(title: str, author: str, lang: str = "ru") -> str:
    language = "русском" if lang == "ru" else "английском"
    return f"""Ты — гастрономический куратор литературных вечеров. Подбери 5–7 блюд
и напитков под атмосферу книги «{title}» ({author}). Названия и описания —
на {language} языке. Не повторяй близкие по смыслу пункты.
"""


def build_aroma_prompt(title: str, author: str, lang: str = "ru") -> str:
    language = "русском" if lang == "ru" else "английском"
    return f"""Ты — парфюмерный куратор. Подбери 4–6 ароматов (свечи, благовония,
эфирные масла) под атмосферу книги «{title}» ({author}). Названия и описания —
на {language} языке. Не повторяй близкие по смыслу пункты.
"""