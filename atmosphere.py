import json
import asyncio

from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic
from openai import AsyncOpenAI
from prompt_config import build_music_prompt

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





def extract_json(raw_text: str) -> dict:
    """Достаём JSON-объект из ответа модели (на случай лишнего текста вокруг)."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    return json.loads(raw_text[start:end + 1])


async def ask_claude(title: str, author: str, lang: str = "ru") -> MusicResult:
    message = await claude_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": build_music_prompt(title, author, lang)}],
    )
    raw_text = ""
    for block in message.content:
        if block.type == "text":
            raw_text = block.text
            break
    return MusicResult.model_validate(extract_json(raw_text))


async def ask_openai(title: str, author: str, lang: str = "ru") -> MusicResult:
    response = await openai_client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": build_music_prompt(title, author, lang)}],
    )
    raw_text = response.choices[0].message.content
    return MusicResult.model_validate(extract_json(raw_text))


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