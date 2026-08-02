"""Как выбирается сигнатура функции промпта (задача 104).

`prompt_config.py` приватный и в git не попадает, поэтому у пользователя может
остаться билдер старой формы `(title, author, lang)` — ломать ему генерацию
нельзя. Раньше совместимость держалась на `try/except TypeError` вокруг вызова,
и это был молчаливый глушитель: ЛЮБАЯ ошибка типов внутри самого промпта
приводила к тихому вызову по старой сигнатуре — генерация уходила без контекста
и без запретов, в логах не оставалось ничего.

Здесь проверяется ровно эта граница: совместимость работает, а настоящие
ошибки видны.
"""

import pytest

from services.ai import _build_with_context

CONTEXT = {"description": "аннотация", "avoid": ["бефстроганов"]}


def test_new_signature_gets_context():
    def build(title, author, lang="ru", context=None):
        return f"{title}|{context['description'] if context else 'нет'}"

    assert _build_with_context(build, "Книга", "Автор", "ru", CONTEXT) == "Книга|аннотация"


def test_old_signature_still_works():
    """Билдер без `context` не должен падать — у пользователя может быть старый
    prompt_config.py, и генерация обязана продолжать работать (без контекста)."""
    def build(title, author, lang="ru"):
        return f"{title}|без контекста"

    assert _build_with_context(build, "Книга", "Автор", "ru", CONTEXT) == "Книга|без контекста"


def test_kwargs_signature_gets_context():
    """`**kwargs` контекст проглотит и не упадёт — считаем такой билдер новым."""
    def build(title, author, lang="ru", **kwargs):
        return f"{title}|{'есть' if kwargs.get('context') else 'нет'}"

    assert _build_with_context(build, "Книга", "Автор", "ru", CONTEXT) == "Книга|есть"


def test_typeerror_inside_prompt_is_not_swallowed():
    """ГЛАВНАЯ проверка задачи 104.

    Ошибка ВНУТРИ промпта должна лететь наружу, а не приводить к тихому вызову
    по старой сигнатуре. Иначе симптом выглядит как «модель не слушается
    запретов», и искать причину приходится в промптах, а не в коде."""
    def build(title, author, lang="ru", context=None):
        return ", ".join(None)          # намеренная ошибка типов

    with pytest.raises(TypeError):
        _build_with_context(build, "Книга", "Автор", "ru", CONTEXT)


def test_no_context_calls_short_form():
    """Контекста нет (например, разовый скрипт) — зовём короткую форму."""
    calls = []

    def build(title, author, lang="ru", context=None):
        calls.append(context)
        return "ok"

    assert _build_with_context(build, "Книга", "Автор", "ru", None) == "ok"
    assert calls == [None]
