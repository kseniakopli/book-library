# Схемы ответов AI (вынесено из services/ai.py — R5, 26.07).
#
# Structured outputs строят по этим моделям JSON-схему, которую провайдер обязан
# заполнить. Отдельный модуль, потому что схемы — самая подвижная часть AI-слоя
# (каждый эксперимент с reasoning-as-schema меняет именно их), а лезть за ними
# приходилось в файл с HTTP-клиентами и метриками.
#
# ⚠ Порядок полей в модели = порядок генерации у модели. Поле-анализ объявляется
# ПЕРВЫМ намеренно (reasoning-as-schema): иначе модель заполняет ответ, не подумав.
import re

from pydantic import BaseModel, Field, field_validator

# --- Схемы ответов AI (structured outputs строит по ним JSON-схему) ---

class Song(BaseModel):
    title: str
    artist: str


class MusicAnalysis(BaseModel):
    """Рабочий анализ книги ПЕРЕД подбором треков (reasoning-as-schema).

    Зачем поле: при structured output модель обязана сразу заполнить схему и
    пропускает «мысленный анализ» из промпта — прыгает прямо к спискам треков,
    угадывая тон по жанру (ироничное городское фэнтези → эпик-дарк-фолк).
    В structured output порядок полей = порядок генерации. Поэтому analysis
    объявлен ПЕРВЫМ: модель сначала обязана назвать интонацию и прилагательные,
    а треки подбирает уже под них. Пользователю это поле не показываем —
    в payload идут только songs (см. atmosphere.CATEGORIES).
    Тот же приём — у еды (FoodAnalysis) и ароматов (AromaAnalysis)."""

    tone: list[str] = []          # прилагательные интонации: ироничная, уютная, осенняя…
    dominant_factor: str = ""     # какой из факторов книги главный (интонация/арка/мир…)
    era_code: str = ""            # музыкальный код эпохи, если она выражена; иначе пусто


class FoodAnalysis(BaseModel):
    """Анализ перед подбором угощений — см. докстринг MusicAnalysis.
    В промпте еды шаг «сначала определи кухню» уже был, но со structured
    output модель его пропускала; теперь кухня — обязательное поле."""

    tone: list[str] = []          # прилагательные интонации вечера
    cuisine: str = ""             # кухня какой страны/региона и эпохи — опора подбора
    dominant_factor: str = ""     # что в книге главное для стола (мир/среда героев/сезон…)


class AromaAnalysis(BaseModel):
    """Анализ перед подбором ароматов — см. докстринг MusicAnalysis."""

    tone: list[str] = []          # прилагательные интонации
    setting: str = ""             # среда/локации книги: лес, море, старая библиотека…
    dominant_factor: str = ""     # что задаёт запах книги (место/сезон/быт героев…)


class MusicResult(BaseModel):
    analysis: MusicAnalysis = Field(default_factory=MusicAnalysis)
    songs: list[Song]
    explanation: str


class AtmosphereItem(BaseModel):
    """Пункт подборки еды/напитков или ароматов: название + короткое описание."""
    title: str
    description: str


class FoodResult(BaseModel):
    analysis: FoodAnalysis = Field(default_factory=FoodAnalysis)
    items: list[AtmosphereItem]
    explanation: str


class AromaResult(BaseModel):
    analysis: AromaAnalysis = Field(default_factory=AromaAnalysis)
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



class RecommendationItem(BaseModel):
    """Совет прочитать книгу, которой у пользователя ещё нет."""
    title: str
    author: str
    reason: str      # почему именно эта — со ссылкой на вкусы читателя


class RecommendationsResult(BaseModel):
    items: list[RecommendationItem]



class InsightsResult(BaseModel):
    """Наблюдения о привычках чтения (задача 24/63)."""
    observations: list[str]



class CsvMapping(BaseModel):
    """Задача 28: какая колонка «грязного» CSV что означает.
    None — такой колонки в файле нет (модели разрешено не найти)."""
    title_column: str
    author_column: str
    rating_column: str | None = None
    read_date_column: str | None = None
    isbn_column: str | None = None

