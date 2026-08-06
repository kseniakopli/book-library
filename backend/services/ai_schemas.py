# Схемы ответов AI (вынесено из services/ai.py — R5, 26.07).
#
# Structured outputs строят по этим моделям JSON-схему, которую провайдер обязан
# заполнить. Отдельный модуль, потому что схемы — самая подвижная часть AI-слоя
# (каждый эксперимент с reasoning-as-schema меняет именно их), а лезть за ними
# приходилось в файл с HTTP-клиентами и метриками.
#
# ⚠ Порядок полей в модели = порядок генерации у модели. Поле-анализ объявляется
# ПЕРВЫМ намеренно (reasoning-as-schema): иначе модель заполняет ответ, не подумав.
import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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

    # --- Запрет как ВЫХОД, а не как вход (з.99, правка 02.08) ---
    #
    # Замер показал: список запрещённых исполнителей доезжает до промпта
    # (проверено scripts/show_prompt.py), модель его читает и всё равно берёт
    # запрещённых — Portishead выросла с 7 книг до 10, будучи в списке.
    # Похоже, перечень из двадцати имён в начале промпта работает подсказкой:
    # мы буквально показываем модели образец «музыки для литературных вечеров»
    # и просим не брать именно его.
    #
    # Приём тот же, что вытащил анализ интонации (reasoning-as-schema): со
    # structured output модель заполняет поля по порядку, поэтому требование
    # выполняется, только если оно ПОЛЕ, а не просьба в тексте. Здесь модель
    # обязана назвать замену до того, как дойдёт до songs.
    # ⚠ Здесь стояло поле replaced_artists («кого заменил и кем»). Убрано 02.08
    # по результатам замера: обе модели вместо замен переписывали в него ВЕСЬ
    # запрещённый список — то есть выписывали двадцать имён канона прямо перед
    # тем, как подбирать треки. Прайминг усилился: Agnes Obel 8→9 книг,
    # Portishead 7→8, при том что обе числились «заменёнными».
    # Урок: поле, которое просит модель пересказать ограничение, работает
    # не как самоконтроль, а как повторное внушение.

    fresh_artists: str = ""
    """Назови 3–5 исполнителей, которых нет ни в запрещённом списке, ни среди
    очевидных для жанра, и объясни одной фразой, чем каждый подходит ЭТОЙ книге.
    Заполняется ДО songs — именно из них собирается основа плейлиста."""


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


# --- Закрытый список шрифтов (01.08) ---
#
# Разведка `scripts/explore_palettes.py` показала: модель называет шрифты
# свободно и выдумывает недоступные — `Freight Text Pro` стоял у 19 книг
# из 201, а это коммерческая гарнитура, в Google Fonts её нет. Отваливается
# молча: <link> не даёт ошибки, книга просто теряет свой шрифт.
# Та же болезнь, что с выдуманными треками, и лечение то же — сверка со
# списком истины. Но здесь сверку можно сделать раньше: не проверять ответ,
# а не дать модели ответить неправильно. Literal уезжает в JSON-схему
# инструмента, и structured output физически не может вернуть чужое имя.
#
# Заодно чинит однообразие: треть книг сидела на Cormorant Garamond, потому
# что список был открытым и модель шла к самому вероятному имени.
#
# ⚠ Все шрифты обязаны быть в Google Fonts И иметь кириллицу — каталог у нас
# русский. Список проверяется страницей `docs/превью_шрифты.html`:
# вставить имена в массив FONTS и посмотреть вердикты. Добавляешь шрифт —
# сначала проверь, потом вписывай.
DESIGN_SERIF_FONTS = (
    "Spectral", "PT Serif", "Cormorant Garamond", "Playfair Display",
    "Literata", "Alegreya", "Vollkorn", "Lora", "Merriweather",
    "Old Standard TT", "Forum", "Oranienbaum", "IBM Plex Serif",
)
# ⚠ Проверено 02.08 на docs/превью_шрифты.html:
# - `Bitter` УБРАН — кириллицы нет. Список изначально собирался по памяти,
#   и это единственная гарнитура, которая не прошла проверку. Успела уехать
#   двум книгам до проверки — их паспорта пересобраны.
# - `Forum` и `Oranienbaum` есть, но БЕЗ жирного начертания: заголовки у них
#   браузер подделает. Оставлены сознательно — оба характерные и с родной
#   кириллицей, а синтетический жирный на дисплейных кеглях терпим.
# Добавляешь шрифт — сначала прогони его через превью.
DESIGN_SANS_FONTS = (
    "Commissioner", "Onest", "Manrope", "Inter", "IBM Plex Sans",
    "Golos Text", "Jost", "Rubik", "Oswald", "Fira Sans",
)
DESIGN_FONTS = DESIGN_SERIF_FONTS + DESIGN_SANS_FONTS


class DesignResult(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _parse_stringified(cls, data):
        """Палитра, пришедшая СТРОКОЙ с JSON внутри, — разобрать, а не ронять.

        Случай 02.08: в батче из десяти книг одна вернула `palette_light`
        как `'{"bg": "#D7DEDC", ...}'` — валидная схема, но обёрнутая в строку.
        Паспорт целиком отбрасывался из-за формы одного поля, книга оставалась
        со старым оформлением. Модель здесь не ошиблась по существу, ошиблась
        в упаковке — это чинится кодом, а не повторной генерацией."""
        if not isinstance(data, dict):
            return data
        for key in ("palette_dark", "palette_light"):
            value = data.get(key)
            if isinstance(value, str):
                try:
                    data[key] = json.loads(value)
                except (TypeError, ValueError):
                    pass
        return data

    base_mood: str
    # Задача 57: две палитры — паспорт живёт в обеих темах интерфейса.
    # Старые сохранённые паспорта имеют одно поле palette (тёмное) —
    # фронт понимает оба формата, а при открытии книги тихо обновляет старый.
    palette_dark: Palette
    palette_light: Palette
    # Literal, а не str: см. комментарий к DESIGN_FONTS выше. Старые
    # сохранённые паспорта в базе не перепроверяются — валидация работает
    # только на генерации, читаются они как есть.
    title_font: Literal[DESIGN_SERIF_FONTS]  # type: ignore[valid-type]
    body_font: Literal[DESIGN_FONTS]  # type: ignore[valid-type]
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


DESIGN_FONT_WINDOW = 0.6   # какую долю списка книга видит при ротации
DESIGN_FONT_MIN_CHOICES = 4


def _rotate(pool: tuple[str, ...], seed: int | None) -> tuple[str, ...]:
    """Поднабор списка, свой у каждой книги.

    Зачем (02.08, перед пересборкой 183 книг). Запрет считается ОДИН раз перед
    батчем, счётчики по ходу не обновляются — значит все книги прогона видят
    одинаковый набор разрешённых шрифтов, и модель спокойно засыпает одним
    именем половину библиотеки: на выборке в 10 книг `Vollkorn` взяли четыре.
    Запрет убирает старых фаворитов, но не мешает завести нового.

    Ротация решает это конструкцией, а не уговором: книга физически не видит
    большей части списка, поэтому одинаковый выбор у соседних книг невозможен.
    Тот же принцип, что и во всех сегодняшних правках, — сделать однообразие
    непредставимым, а не просить его избегать."""
    if seed is None or len(pool) <= DESIGN_FONT_MIN_CHOICES:
        return pool
    size = max(DESIGN_FONT_MIN_CHOICES, round(len(pool) * DESIGN_FONT_WINDOW))
    start = seed % len(pool)
    doubled = pool + pool          # окно может перехлёстывать через конец
    return tuple(doubled[start:start + size])


def design_result_without(fonts: list[str] | None, seed: int | None = None):
    """`DesignResult`, в котором затасканные шрифты ВЫЧЕРКНУТЫ из Literal.

    Зачем (з.101, замер 02.08). Список `avoid_fonts` в тексте промпта модель
    проигнорировала: `IBM Plex Serif` лежал в запрете и всё равно оказался
    у 8 книг из 10, уникальных вышло два на десять. Ровно то же было
    с запретом исполнителей в музыке — перечисление в промпте не работает.
    А `Literal` сработал с первого раза: выдуманные гарнитуры исчезли мгновенно,
    потому что стали НЕПРЕДСТАВИМЫ в схеме. Значит и «не бери затасканное»
    надо выражать так же — сузив сам список на время запроса, а не прося
    воздержаться. Промпт задаёт направление, схема держит границы.

    ⚠ Пустой набор недопустим: вычеркнув всё, мы не оставим модели допустимого
    ответа. Долю ограничивает `prompt_context.AVOID_FONT_MAX_SHARE`, а здесь
    стоит последняя страховка — при пустом остатке возвращаем полную схему."""
    banned = {f.strip() for f in (fonts or [])}
    serif = _rotate(tuple(f for f in DESIGN_SERIF_FONTS if f not in banned), seed)
    # Текстовому шрифту сдвигаем окно иначе, иначе оба поля видят один участок
    # списка и снова сходятся (та же ошибка, что была в enforce_fonts).
    body = _rotate(
        tuple(f for f in DESIGN_FONTS if f not in banned),
        None if seed is None else seed + 5,
    )
    if not serif or not body:
        return DesignResult

    class NarrowedDesignResult(DesignResult):
        title_font: Literal[serif]  # type: ignore[valid-type]
        body_font: Literal[body]    # type: ignore[valid-type]

    return NarrowedDesignResult


def enforce_fonts(design, banned: list[str] | None, seed: int) -> list[str]:
    """Заменить запрещённые шрифты разрешёнными. Правит `design` на месте,
    возвращает список произведённых замен (для лога).

    Зачем (02.08). `enum` в схеме инструмента — это ПОДСКАЗКА, а не гарантия:
    модель может вернуть значение вне списка. В синхронном пути его отсекает
    валидация, а батч разбирал ответ широкой схемой — и `IBM Plex Serif`,
    лежавший в запрете, достался трём книгам из десяти.
    Отвергать такой паспорт целиком жалко: книга осталась бы со старым
    оформлением из-за одного поля. Поэтому исправляем, как с несуществующими
    треками в Spotify, — код правит вывод модели, а не отказывается от него.

    Выбор замены детерминированный (по id книги), чтобы прогон повторялся
    и чтобы замены расходились по разным книгам, а не сходились в одну."""
    blocked = {f.strip() for f in (banned or [])}
    swaps = []
    # Смещения разные, иначе оба поля попадают в один индекс: полный список
    # НАЧИНАЕТСЯ с засечных, и при малых id заголовочный и текстовый шрифт
    # выходили одинаковыми (5 случаев из 9 в прогоне 02.08). Плюс текстовый
    # выбираем, исключив уже выбранный заголовочный.
    for field, pool, offset in (
        ("title_font", DESIGN_SERIF_FONTS, 0),
        ("body_font", DESIGN_FONTS, 5),
    ):
        current = (getattr(design, field, "") or "").strip()
        if current not in blocked:
            continue
        taken = {(getattr(design, "title_font", "") or "").strip()} if field == "body_font" else set()
        allowed = [f for f in pool if f not in blocked and f not in taken]
        if not allowed:
            continue
        replacement = allowed[(seed + offset) % len(allowed)]
        object.__setattr__(design, field, replacement)
        swaps.append(f"{field}: {current} → {replacement}")
    return swaps


class RecommendationItem(BaseModel):
    """Совет прочитать книгу, которой у пользователя ещё нет.

    ⚠ `genre` стоит ПЕРВЫМ полем намеренно (задача 126, приём
    reasoning-as-schema): порядок полей равен порядку генерации, и модель
    вынуждена назвать жанр ДО того, как выберет книгу. Просьба «советуй
    фэнтези», стоявшая в конце промпта, 06.08 дала одно фэнтези из девяти —
    модель соглашалась, а потом предлагала что хотела.
    Побочная польза: видно, ЧТО она считает фэнтези, и можно померить долю
    попаданий вместо «кажется, стало лучше».
    """
    genre: str       # жанр советуемой книги — словами модели
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

