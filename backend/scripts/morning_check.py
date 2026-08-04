"""Проверки начала рабочего дня (04.08).

Четыре вопроса, ответы на которые дешевле получить ДО начала работы,
чем в середине:

  1. Не разъехались ли документы (`docs_audit.py`).
  2. Где я остановилась — незакоммиченный хвост и что не выложено на прод.
  3. Делаются ли бэкапы. **Главный пункт:** `backup_db.py` запускает
     Планировщик Windows, а такие механизмы отваливаются МОЛЧА — обновление
     системы, переименованная папка, смена пароля учётки. Узнать об этом
     в момент, когда бэкап понадобился, — худший из возможных вариантов.
  4. Жив ли прод (заодно будит уснувшую машину Fly).
  5. Не отстала ли рабочая память ассистента от кода.

Запуск из `backend/`:  python scripts/morning_check.py
Без обращения к сети:  python scripts/morning_check.py --offline

⚠ Скрипт НИЧЕГО не меняет и не падает целиком из-за одной проверки: каждая
отчитывается сама за себя. Пустой результат обязан означать «чисто», а не
«не смог посмотреть», поэтому у каждой проверки есть состояние «не знаю»,
и оно печатается отдельно от «всё хорошо».
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
BACKUP_DIR = BACKEND / "backups"

# Домен заморожен печатным тиражом (QR карточек, 28.07) — он не изменится
# сам по себе. Переезд потребует правки и здесь, и в `make_landing_qr.py`.
PROD_HEALTH = "https://nocturne-library.fly.dev/health"

# Бэкап раз в сутки; двое — это уже пропущенный запуск, а не выходной ритм.
BACKUP_STALE_DAYS = 2

OK, WARN, UNKNOWN = "  ✔", "  ⚠", "  ?"


def run_git(*args: str) -> str | None:
    """Git только на чтение. None означает «не смог спросить»."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


# --- 1. документы -----------------------------------------------------------

def check_docs() -> bool:
    print("\n1. Документы")
    script = BACKEND / "scripts" / "docs_audit.py"
    if not script.exists():
        print(f"{UNKNOWN} нет {script.name} — проверить нечем")
        return False
    try:
        done = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{UNKNOWN} не удалось запустить docs_audit: {exc}")
        return False

    total = re.search(r"Всего находок: (\d+)", done.stdout)
    if done.returncode == 2 or total is None:
        print(f"{UNKNOWN} docs_audit не отработал (код {done.returncode})")
        return False
    if total.group(1) == "0":
        print(f"{OK} расхождений нет")
        return True

    print(f"{WARN} находок: {total.group(1)} — подробности:")
    print("       cd backend && python scripts/docs_audit.py")
    for line in done.stdout.splitlines():
        if line.startswith("  ") and not line.startswith("  …"):
            print("   " + line.strip()[:100])
    return False


# --- 2. где я остановилась --------------------------------------------------

def check_git() -> bool:
    print("\n2. Состояние работы")
    status = run_git("status", "--short")
    if status is None:
        print(f"{UNKNOWN} git не ответил")
        return False

    clean = True
    if status:
        n = len(status.splitlines())
        print(f"{WARN} незакоммиченных файлов: {n}")
        for line in status.splitlines()[:8]:
            print("      " + line)
        clean = False
    else:
        print(f"{OK} рабочее дерево чистое")

    # что накопилось сверх последней выкладки: тег — единственный надёжный
    # признак, дата в его имени врёт (заход после полуночи, 04.08)
    tag = run_git("describe", "--tags", "--abbrev=0", "--match", "prod-*")
    if tag is None:
        print(f"{UNKNOWN} прод-тегов нет — не с чем сравнивать")
        return clean

    pending = run_git("log", "--oneline", f"{tag}..HEAD")
    if pending:
        rows = pending.splitlines()
        print(f"{WARN} не выложено после {tag}: {len(rows)} коммит(ов)")
        for line in rows[:8]:
            print("      " + line)
        clean = False
    else:
        print(f"{OK} всё выложено (последний тег {tag})")

    unpushed = run_git("log", "--oneline", "@{u}..HEAD")
    if unpushed:
        print(f"{WARN} не запушено: {len(unpushed.splitlines())} коммит(ов)")
        clean = False
    return clean


# --- 3. бэкапы --------------------------------------------------------------

def check_backups() -> bool:
    print("\n3. Бэкапы базы")
    if not BACKUP_DIR.is_dir():
        print(f"{WARN} папки {BACKUP_DIR} нет — бэкапы не делались ни разу")
        return False

    files = sorted(BACKUP_DIR.glob("library-*.db"))
    if not files:
        print(f"{WARN} в {BACKUP_DIR.name}/ пусто")
        return False

    newest = max(files, key=lambda p: p.stat().st_mtime)
    made = datetime.fromtimestamp(newest.stat().st_mtime)
    age = datetime.now() - made
    size_mb = newest.stat().st_size / 1024 / 1024

    if age > timedelta(days=BACKUP_STALE_DAYS):
        print(f"{WARN} последний бэкап {made:%d.%m %H:%M} — {age.days} дн. назад")
        print("       Планировщик Windows мог отвалиться молча. Проверить задачу,")
        print("       разово: cd backend && python scripts/backup_db.py")
        return False

    print(f"{OK} последний {made:%d.%m %H:%M} ({size_mb:.1f} МБ), всего копий {len(files)}")
    return True


# --- 4. прод ----------------------------------------------------------------

def check_prod() -> bool:
    print("\n4. Прод")
    try:
        with urllib.request.urlopen(PROD_HEALTH, timeout=25) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        print(f"{WARN} {PROD_HEALTH} отвечает {exc.code}")
        return False
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        # Отличаем «прод лежит» от «у меня нет сети» — это разные новости
        print(f"{UNKNOWN} не достучались: {exc}. Проверить сеть, потом прод")
        return False

    if code == 200:
        print(f"{OK} отвечает 200 (машина разбужена)")
        return True
    print(f"{WARN} отвечает {code}")
    return False


# --- 5. рабочая память ассистента -------------------------------------------

def check_context() -> bool:
    """Насколько `Контекст_проекта.md` отстал от кода.

    ⚠ Скрипт НЕ измеряет состояние ассистента — этого не видит никто, включая
    его самого: деградация длинной сессии в том и состоит, что уверенность
    сохраняется, а точность падает. Измеряется косвенное и проверяемое —
    расхождение между файлом-онбордингом и репозиторием. Чем оно больше,
    тем больше ассистент опирается на «помню, как устроено».
    """
    print("\n5. Рабочая память")
    ctx = REPO / "docs" / "Контекст_проекта.md"
    if not ctx.exists():
        print(f"{UNKNOWN} нет docs/Контекст_проекта.md — переезд в новую сессию вслепую")
        return False

    ok = True

    # дата в шапке файла — то, что ассистент считает «сегодня»
    head = ctx.read_text(encoding="utf-8")[:2000]
    stamp = re.search(r"Актуально на (\d{2})\.(\d{2})\.(\d{4})", head)
    if stamp:
        day, month, year = (int(x) for x in stamp.groups())
        behind = (datetime.now() - datetime(year, month, day)).days
        if behind > 2:
            print(f"{WARN} шапка говорит «актуально на {day:02d}.{month:02d}» — {behind} дн. назад")
            ok = False
        else:
            print(f"{OK} шапка свежая ({day:02d}.{month:02d})")
    else:
        print(f"{UNKNOWN} в шапке нет строки «Актуально на …»")
        ok = False

    # сколько кода приехало после последней правки файла
    since = datetime.fromtimestamp(ctx.stat().st_mtime).isoformat()
    log = run_git("log", "--oneline", f"--since={since}")
    if log is None:
        print(f"{UNKNOWN} git не ответил — не с чем сравнить")
        return False
    count = len(log.splitlines()) if log else 0
    if count > 10:
        print(f"{WARN} после последней правки контекста — {count} коммит(ов)")
        ok = False
    else:
        print(f"{OK} после последней правки контекста {count} коммит(ов)")

    print("\n   Признаки, что пора в НОВУЮ сессию (замечает человек, не скрипт):")
    print("   · ассистент ошибся в факте о коде, который раньше проверял;")
    print("   · сослался на файл или поле, которых нет;")
    print("   · предложил сделать то, что уже сделано сегодня;")
    print("   · пересказывает по памяти вместо того, чтобы открыть файл.")
    print("   Первый же такой случай — повод переехать: дальше будет чаще.")
    return ok


# --- вывод ------------------------------------------------------------------

def main() -> int:
    print(f"Проверки начала дня — {datetime.now():%d.%m.%Y %H:%M}")

    results = [check_docs(), check_git(), check_backups()]
    if "--offline" in sys.argv:
        print("\n4. Прод — пропущено (--offline)")
    else:
        results.append(check_prod())
    results.append(check_context())

    bad = results.count(False)
    print()
    if bad:
        print(f"Требует внимания: {bad} из {len(results)}.")
        print("Это не запрет работать — это список того, что дешевле")
        print("починить сейчас, чем в середине задачи.")
    else:
        print("Всё чисто. Можно работать.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
