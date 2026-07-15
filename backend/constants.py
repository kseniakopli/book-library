# Единое место для «магических строк» (рефакторинг R3).
# Категории атмосферы живут в routers/atmosphere.py (CATEGORIES) —
# там им нужны генераторы, здесь были бы циклические импорты.

# --- статусы чтения ---
STATUS_WANT = "want"
STATUS_READING = "reading"
STATUS_READ = "read"
ALLOWED_STATUSES = {STATUS_WANT, STATUS_READING, STATUS_READ}

# --- статусы фонового обогащения ---
ENRICH_PENDING = "pending"
ENRICH_READY = "ready"
ENRICH_FAILED = "failed"

# --- AI-источники ---
SOURCE_CLAUDE = "Claude"
SOURCE_CHATGPT = "ChatGPT"

# --- имена событий (события — append-only, имена менять нельзя) ---
EVENT_BOOK_ADDED = "book_added"
EVENT_BOOK_DELETED = "book_deleted"
EVENT_STATUS_CHANGED = "status_changed"
EVENT_RATED = "rated"
EVENT_ENRICHED = "enriched"
EVENT_SEARCH = "search"
EVENT_IMPORT = "import"
EVENT_AI_MUSIC = "ai_music_generated"
EVENT_AI_DESIGN = "ai_design_generated"
EVENT_AI_FOOD = "ai_food_generated"
EVENT_AI_AROMA = "ai_aroma_generated"
