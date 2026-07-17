# Разбор «Даты прочтения» из CSV (задача 1). Формат у людей гибкий:
# «Июль 2026 г.», «2026-07-14», «14.07.2026», просто «2026».
import re
from datetime import datetime
from typing import Optional

# Порядок важен: длинные/однозначные префиксы раньше, чтобы «март» не
# перехватился по «ма» (май)
_MONTHS = [
    ("сентябр", 9), ("феврал", 2), ("октябр", 10), ("декабр", 12),
    ("январ", 1), ("апрел", 4), ("август", 8), ("ноябр", 11),
    ("март", 3), ("июн", 6), ("июл", 7), ("мая", 5), ("май", 5),
]


def parse_read_date(raw: Optional[str]) -> Optional[datetime]:
    """Дата из свободного текста; не разобрали — None (книга останется
    прочитанной, просто без даты)."""
    if not raw:
        return None
    s = raw.strip().lower()

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    year_match = re.search(r"(19|20)\d{2}", s)
    if year_match:
        year = int(year_match.group())
        for name, month in _MONTHS:
            if name in s:
                return datetime(year, month, 1)
        return datetime(year, 1, 1)   # только год — первое января

    return None
