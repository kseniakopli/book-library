# AI-генераторы атмосферы.
# Контракт генераторов: async (title, author, lang) -> {источник: Pydantic-модель}
# (для дизайна словарь собирает обёртка в routers/atmosphere.py).
import asyncio
import re

from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
import anthropic
from openai import AsyncOpenAI

from constants import SOURCE_CHATGPT, SOURCE_CLAUDE
import prompt_config
from prompt_config import (
    build_aroma_prompt,
    build_design_prompt,
    build_food_prompt,
    build_music_prompt,
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
claude_client = anthropic.AsyncAnthropic()
openai_client = AsyncOpenAI()


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
    palette: Palette
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


# --- Обобщённые вызовы провайдеров (7.1): промпт и модель — параметры ---

async def ask_claude(prompt: str, output_model, max_tokens: int = 8000):
    message = await claude_client.messages.parse(
        model="claude-sonnet-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_format=output_model,
    )
    if message.parsed_output is None:
        raise ValueError(
            f"Claude: пустой parsed_output (stop_reason={message.stop_reason})"
        )
    return message.parsed_output


async def ask_openai(prompt: str, output_model):
    response = await openai_client.chat.completions.parse(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format=output_model,
    )
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


def make_two_source_generator(build_prompt, result_model, fallback_factory):
    """Генератор категории «спросить оба AI параллельно» (music, food, aroma).
    Новая категория = промпт + модель результата + эта фабрика."""
    async def generate(title: str, author: str, lang: str = "ru") -> dict:
        prompt = _with_style(build_prompt(title, author, lang))
        claude_result, openai_result = await asyncio.gather(
            safe_ask(ask_claude(prompt, result_model), fallback_factory),
            safe_ask(ask_openai(prompt, result_model), fallback_factory),
        )
        return {SOURCE_CLAUDE: claude_result, SOURCE_CHATGPT: openai_result}
    return generate


FAILED_TEXT = "(не удалось получить ответ)"

generate_music = make_two_source_generator(
    build_music_prompt, MusicResult,
    lambda: MusicResult(songs=[], explanation=FAILED_TEXT),
)
generate_food = make_two_source_generator(
    build_food_prompt, FoodResult,
    lambda: FoodResult(items=[], explanation=FAILED_TEXT),
)
generate_aroma = make_two_source_generator(
    build_aroma_prompt, AromaResult,
    lambda: AromaResult(items=[], explanation=FAILED_TEXT),
)


async def generate_design(title: str, author: str, lang: str = "ru") -> DesignResult:
    """Дизайн-паспорт (палитра, шрифты, символ) — одним источником (Claude).
    max_tokens с запасом: SVG-символ бывает многословным."""
    return await ask_claude(
        _with_style(build_design_prompt(title, author, lang)),
        DesignResult,
        max_tokens=8000,
    )