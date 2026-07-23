# Единое место для «магических строк» (рефакторинг R3).
# Категории атмосферы живут в services/atmosphere.py (CATEGORIES) —
# там им нужны генераторы, здесь были бы циклические импорты.

# --- статусы чтения ---
STATUS_WANT = "want"
STATUS_READING = "reading"
STATUS_READ = "read"
ALLOWED_STATUSES = {STATUS_WANT, STATUS_READING, STATUS_READ}

# --- статусы цикла книг (задача 89) ---
SERIES_READING = "reading"      # читаю
SERIES_READ = "read"            # прочитан
SERIES_DROPPED = "dropped"      # перестала читать
ALLOWED_SERIES_STATUSES = {SERIES_READING, SERIES_READ, SERIES_DROPPED}
# Порядок на полке: читаю → прочитано → перестала читать (решение Ксении 22.07)
SERIES_STATUS_ORDER = {SERIES_READING: 0, SERIES_READ: 1, SERIES_DROPPED: 2}

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
EVENT_BOOK_EDITED = "book_edited"      # задача 3: ручная правка полей
EVENT_STATUS_CHANGED = "status_changed"
EVENT_RATED = "rated"
EVENT_ENRICHED = "enriched"
EVENT_SEARCH = "search"
EVENT_IMPORT = "import"
EVENT_AI_MUSIC = "ai_music_generated"
EVENT_TRACK_REMOVED = "track_removed"  # точечное удаление трека админом
EVENT_AI_DESIGN = "ai_design_generated"
EVENT_AI_FOOD = "ai_food_generated"
EVENT_AI_AROMA = "ai_aroma_generated"
EVENT_AI_RECOMMENDATIONS = "ai_recommendations_generated"   # этап 8
EVENT_AI_INSIGHTS = "ai_insights_generated"                 # задача 24/63
EVENT_PLAYLIST_CREATED = "spotify_playlist_created"
EVENT_BACKFILL = "backfill_scheduled"
