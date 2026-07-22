# AI-генераторы атмосферы.
# Контракт генераторов: async (title, author, lang) -> {источник: Pydantic-модель}
# (для дизайна словарь собирает обёртка в services/atmosphere.py).
import asyncio
import contextvars
import re
from time import perf_counter

from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
import anthropic
from openai import AsyncOpenAI

from constants import SOURCE_CHATGPT, SOURCE_CLAUDE
import prompt_config
from prompt_config import (
    build_aroma_prompt,
    build_csv_mapping_prompt,
    build_design_prompt,
    build_food_prompt,
    build_insights_prompt,
    build_music_prompt,
    build_recommendations_prompt,
)


def _with_style(prompt: str) -> str:
    """Общие правила стиля (STYLE_RULES из prompt_config) дописываются
    к КАЖДОМУ AI-запросу — единая точка, категории про неё не знают.
    Константа необязательна: нет — промпт уходит как есть."""
    rules = getattr(prompt_config, "STYLE_RULES", "").strip()
    if not rules:
        return prompt
    return f"{prompt.rstrip()}\n\nОбщие правила стиля (обязательны):\n{rules}"

load_dotenv()                       # читаем ключи из .env
# Задача 54: таймаут 90с — зависший провайдер даёт заглушку через safe_ask,
# а не подвисший на минуты запрос фронта (дефолт SDK — до 10 минут)
claude_client = anthropic.AsyncAnthropic(timeout=90)
openai_client = AsyncOpenAI(timeout=90)


# --- Схемы ответов AI (structured outputs строит по ним JSON-схему) ---

class Song(BaseModel):
    title: str
    artist: str


class MusicResult(BaseModel):
    songs: list[Song]
    explanation: str


class AtmosphereItem(BaseModel):
    """Пункт подборки еды/напитков или ароматов: название + короткое описание."""
    title: str
    description: str


class FoodResult(BaseModel):
    items: list[AtmosphereItem]
    explanation: str


class AromaResult(BaseModel):
    items: list[AtmosphereItem]
    explanation: str


HEX_COLOR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
FONT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ]{0,48}$")

# Запрещённые фрагменты в SVG (задача 37 для символа): скрипты, обработчики,
# внешние ссылки. Рендерим через <img data:>, где это и так не исполняется,
# но границу держим и на бэкенде.
SVG_FORBIDDEN = (
    "<script", "javascript:", "onload", "onclick", "onerror",
    "<foreignobject", "<image", "href=",
)
MAX_SVG_CHARS = 20_000


class Palette(BaseModel):
    bg: str
    surface: str
    accent: str
    text: str
    muted: str

    # Security (задача 37): цвета уходят в inline-стили карточки.
    @field_validator("bg", "surface", "accent", "text", "muted")
    @classmethod
    def _hex_only(cls, v: str) -> str:
        v = v.strip()
        if not HEX_COLOR.match(v):
            raise ValueError(f"не hex-цвет: {v!r}")
        return v


class DesignResult(BaseModel):
    base_mood: str
    # Задача 57: две палитры — паспорт живёт в обеих темах интерфейса.
    # Старые сохранённые паспорта имеют одно поле palette (тёмное) —
    # фронт понимает оба формата, а при открытии книги тихо обновляет старый.
    palette_dark: Palette
    palette_light: Palette
    title_font: str
    body_font: str
    statement: str
    symbol_svg: str   # минималистичный векторный символ книги («экслибрис»)

    @field_validator("title_font", "body_font")
    @classmethod
    def _safe_font(cls, v: str) -> str:
        v = v.strip()
        if not FONT_NAME.match(v):
            raise ValueError(f"недопустимое имя шрифта: {v!r}")
        return v

    @field_validator("symbol_svg")
    @classmethod
    def _safe_svg(cls, v: str) -> str:
        v = v.strip()
        if len(v) > MAX_SVG_CHARS:
            raise ValueError("SVG слишком большой")
        low = v.lower()
        if not (low.startswith("<svg") and low.endswith("</svg>")):
            raise ValueError("symbol_svg должен быть одним элементом <svg>…</svg>")
        if any(token in low for token in SVG_FORBIDDEN):
            raise ValueError("SVG содержит запрещённые элементы")
        return v


# --- Метрики AI-вызовов (задача 80) ---
# Каждый ask_* пишет в буфер провайдера, латентность и usage tokens — событийный
# лог получает «сколько стоил этот запрос и кто отвечал быстрее».
# ContextVar, а не глобальный список: параллельные HTTP-запросы (панель атмосферы
# генерирует все категории разом) не перемешивают чужие метрики.
_ai_metrics: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "ai_metrics", default=None
)


def start_ai_metrics() -> None:
    """Начать сбор метрик (вызывается перед генерацией, обычно в роутере)."""
    _ai_metrics.set([])


def take_ai_metrics() -> list[dict]:
    """Забрать собранное и остановить сбор. Без start_* вернёт []."""
    metrics = _ai_metrics.get() or []
    _ai_metrics.set(None)
    return metrics


def _record_metric(entry: dict) -> None:
    metrics = _ai_metrics.get()
    if metrics is not None:
        metrics.append(entry)


# --- Обобщённые вызовы провайдеров (7.1): промпт и модель — параметры ---

async def ask_claude(
    prompt: str, output_model, max_tokens: int = 8000, temperature: float | None = None
):
    start = perf_counter()
    # temperature задаётся не всегда: для музыки повыше — против «одинаковых
    # атмосферных» подборок (mode collapse: модель тянет клише вроде
    # Sigur Rós / Massive Attack в каждую книгу). Для дизайна/инсайтов не трогаем.
    extra = {} if temperature is None else {"temperature": temperature}
    try:
        message = await claude_client.messages.parse(
            model="claude-sonnet-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            output_format=output_model,
            **extra,
        )
    except Exception as e:
        _record_metric({
            "provider": SOURCE_CLAUDE,
            "latency_ms": round((perf_counter() - start) * 1000),
            "error": type(e).__name__,
        })
        raise
    _record_metric({
        "provider": SOURCE_CLAUDE,
        "latency_ms": round((perf_counter() - start) * 1000),
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    })
    if message.parsed_output is None:
        raise ValueError(
            f"Claude: пустой parsed_output (stop_reason={message.stop_reason})"
        )
    return message.parsed_output


async def ask_openai(prompt: str, output_model, temperature: float | None = None):
    start = perf_counter()
    extra = {} if temperature is None else {"temperature": temperature}
    try:
        response = await openai_client.chat.completions.parse(
            model="gpt-5.4-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format=output_model,
            **extra,
        )
    except Exception as e:
        _record_metric({
            "provider": SOURCE_CHATGPT,
            "latency_ms": round((perf_counter() - start) * 1000),
            "error": type(e).__name__,
        })
        raise
    usage = response.usage
    _record_metric({
        "provider": SOURCE_CHATGPT,
        "latency_ms": round((perf_counter() - start) * 1000),
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
    })
    choice = response.choices[0]
    if choice.message.parsed is None:
        raise ValueError(
            f"OpenAI: пустой parsed (finish_reason={choice.finish_reason}, "
            f"refusal={choice.message.refusal})"
        )
    return choice.message.parsed


async def safe_ask(coro, fallback_factory):
    """Если один AI упал — не роняем весь запрос, отдаём пустой результат."""
    try:
        return await coro
    except Exception as e:
        print("Ошибка одного из AI:", e)
        return fallback_factory()


def make_two_source_generator(
    build_prompt, result_model, fallback_factory, temperature: float | None = None
):
    """Генератор категории «спросить оба AI параллельно» (music, food, aroma).
    Новая категория = промпт + модель результата + эта фабрика.
    temperature — общий рычаг разнообразия (для музыки выше, см. generate_music)."""
    async def generate(title: str, author: str, lang: str = "ru") -> dict:
        prompt = _with_style(build_prompt(title, author, lang))
        claude_result, openai_result = await asyncio.gather(
            safe_ask(ask_claude(prompt, result_model, temperature=temperature), fallback_factory),
            safe_ask(ask_openai(prompt, result_model, temperature=temperature), fallback_factory),
        )
        return {SOURCE_CLAUDE: claude_result, SOURCE_CHATGPT: openai_result}
    return generate


FAILED_TEXT = "(не удалось получить ответ)"

# Повышенная температура против «одинаковых подборок» (mode collapse: модель
# тянет одни и те же безопасные варианты в каждую книгу — Sigur Rós в музыке,
# «мясо с корнеплодами» в еде). Дизайн/инсайты не трогаем: там разнообразие вредно.
# Музыка выше еды: выдумки в музыке всё равно отсеет резолв в Spotify
# (services/atmosphere.verify_music_results), а у еды фильтра нет — не гоним.
MUSIC_TEMPERATURE = 1.0
FOOD_TEMPERATURE = 0.9
AROMA_TEMPERATURE = 0.9

generate_music = make_two_source_generator(
    build_music_prompt, MusicResult,
    lambda: MusicResult(songs=[], explanation=FAILED_TEXT),
    temperature=MUSIC_TEMPERATURE,
)
generate_food = make_two_source_generator(
    build_food_prompt, FoodResult,
    lambda: FoodResult(items=[], explanation=FAILED_TEXT),
    temperature=FOOD_TEMPERATURE,
)
generate_aroma = make_two_source_generator(
    build_aroma_prompt, AromaResult,
    lambda: AromaResult(items=[], explanation=FAILED_TEXT),
    temperature=AROMA_TEMPERATURE,
)


class RecommendationItem(BaseModel):
    """Совет прочитать книгу, которой у пользователя ещё нет."""
    title: str
    author: str
    reason: str      # почему именно эта — со ссылкой на вкусы читателя


class RecommendationsResult(BaseModel):
    items: list[RecommendationItem]


async def generate_recommendations(
    favorites: list[str], exclude: list[str], count: int = 5, lang: str = "ru"
) -> dict:
    """Этап 8: рекомендации новых книг по высоко оценённым — от ОБОИХ моделей
    (20.07), как в атмосфере: интереснее сравнивать, и вкусы у них разные.
    `favorites` — «Название — Автор (оценка)», `exclude` — что уже в библиотеке
    (модель просят не повторять; дедуп между источниками — в роутере).
    Контракт как у генераторов атмосферы: {источник: RecommendationsResult}.
    Один провайдер упал — второй всё равно даст советы (safe_ask)."""
    prompt = _with_style(build_recommendations_prompt(favorites, exclude, count, lang))
    empty = lambda: RecommendationsResult(items=[])   # noqa: E731
    claude_result, openai_result = await asyncio.gather(
        safe_ask(ask_claude(prompt, RecommendationsResult), empty),
        safe_ask(ask_openai(prompt, RecommendationsResult), empty),
    )
    return {SOURCE_CLAUDE: claude_result, SOURCE_CHATGPT: openai_result}


class InsightsResult(BaseModel):
    """Наблюдения о привычках чтения (задача 24/63)."""
    observations: list[str]


async def generate_insights(summary: str, lang: str = "ru") -> InsightsResult:
    """Комментарий к статистике. Цифры считает бэкенд, модель только их толкует —
    так в тексте не появится чисел, которых нет в сводке.
    max_tokens небольшой: ответ — несколько предложений."""
    return await ask_claude(
        _with_style(build_insights_prompt(summary, lang)),
        InsightsResult,
        max_tokens=1000,
    )


class CsvMapping(BaseModel):
    """Задача 28: какая колонка «грязного» CSV что означает.
    None — такой колонки в файле нет (модели разрешено не найти)."""
    title_column: str
    author_column: str
    rating_column: str | None = None
    read_date_column: str | None = None
    isbn_column: str | None = None


async def map_csv_columns(
    headers: list[str], sample_rows: list[dict], lang: str = "ru"
) -> CsvMapping:
    """Распознать роли колонок CSV с нестандартными заголовками.
    Модель видит заголовки и 2–3 строки-примера; ответ — строгий JSON по схеме.
    Валидация «колонка существует» — на вызывающей стороне (routers/imports.py):
    модель может вернуть выдуманное имя, доверять без проверки нельзя."""
    return await ask_claude(
        build_csv_mapping_prompt(headers, sample_rows, lang),
        CsvMapping,
        max_tokens=500,
    )


async def generate_design(title: str, author: str, lang: str = "ru") -> DesignResult:
    """Дизайн-паспорт (палитра, шрифты, символ) — одним источником (Claude).
    max_tokens с запасом: SVG-символ бывает многословным."""
    return await ask_claude(
        _with_style(build_design_prompt(title, author, lang)),
        DesignResult,
        max_tokens=8000,
    )