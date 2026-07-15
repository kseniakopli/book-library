import asyncio
import re
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
import anthropic
from openai import AsyncOpenAI
from prompt_config import build_music_prompt, build_design_prompt

load_dotenv()                       # читаем ключи из .env
claude_client = anthropic.AsyncAnthropic()
openai_client = AsyncOpenAI()


# --- Схема ответа AI (по ней строго разбираем JSON) ---
class Song(BaseModel):
    title: str
    artist: str


class MusicResult(BaseModel):
    songs: list[Song]
    explanation: str

HEX_COLOR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
FONT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ]{0,48}$")


class Palette(BaseModel):
    bg: str
    surface: str
    accent: str
    text: str
    muted: str

    # Security (задача 37): цвета уходят в inline-стили карточки.
    # Пропускаем только hex — AI-ответ не сможет протащить url(...) и прочее.
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

    # Имена шрифтов подставляются в URL Google Fonts — только буквы/цифры/пробелы
    @field_validator("title_font", "body_font")
    @classmethod
    def _safe_font(cls, v: str) -> str:
        v = v.strip()
        if not FONT_NAME.match(v):
            raise ValueError(f"недопустимое имя шрифта: {v!r}")
        return v




async def ask_claude(title: str, author: str, lang: str = "ru") -> MusicResult:
    message = await claude_client.messages.parse(
        model="claude-sonnet-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": build_music_prompt(title, author, lang)}],
        output_format=MusicResult,   # SDK сам превратит Pydantic-модель в JSON-схему
    )
    if message.parsed_output is None:
        raise ValueError(
            f"Claude: пустой parsed_output (stop_reason={message.stop_reason})"
        )
    return message.parsed_output


async def ask_openai(title: str, author: str, lang: str = "ru") -> MusicResult:
    response = await openai_client.chat.completions.parse(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": build_music_prompt(title, author, lang)}],
        response_format=MusicResult,
    )
    choice = response.choices[0]
    if choice.message.parsed is None:
        raise ValueError(
            f"OpenAI: пустой parsed (finish_reason={choice.finish_reason}, "
            f"refusal={choice.message.refusal})"
        )
    return choice.message.parsed


async def safe_ask(func, title: str, author: str, lang: str) -> MusicResult:
    """Если один AI упал — не роняем весь запрос, отдаём пустой результат."""
    try:
        return await func(title, author, lang)
    except Exception as e:
        print("Ошибка одного из AI:", e)
        return MusicResult(songs=[], explanation="(не удалось получить ответ)")


async def generate_music(title: str, author: str, lang: str = "ru") -> dict:
    """Спрашиваем оба AI параллельно.
    Возвращаем {'Claude': MusicResult, 'ChatGPT': MusicResult}."""
    claude_result, openai_result = await asyncio.gather(
        safe_ask(ask_claude, title, author, lang),
        safe_ask(ask_openai, title, author, lang),
    )
    return {"Claude": claude_result, "ChatGPT": openai_result}

async def ask_claude_design(title: str, author: str, lang: str = "ru") -> DesignResult:
    message = await claude_client.messages.parse(
        model="claude-sonnet-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": build_design_prompt(title, author, lang)}],
        output_format=DesignResult,
    )
    if message.parsed_output is None:
        raise ValueError(
            f"Claude: пустой parsed_output (stop_reason={message.stop_reason})"
        )
    return message.parsed_output


async def generate_design(title: str, author: str, lang: str = "ru") -> DesignResult:
    """Дизайн-паспорт делаем одним источником (Claude) — оформление у книги одно."""
    return await ask_claude_design(title, author, lang)