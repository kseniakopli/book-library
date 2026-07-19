# Снимок OpenAPI-схемы в documentation/openapi.json (задача 72).
#
# Зачем: схема — публичный контракт API. Зафиксированный в git снимок позволяет
# увидеть непреднамеренные breaking changes обычным диффом («ой, поле пропало»),
# не поднимая сервер.
#
# Запуск из backend/ (нужны .env и prompt_config.py — импортируется приложение):
#   python dump_openapi.py
#
# После правок API — перегенерировать и закоммитить вместе с изменениями кода.
import json
from pathlib import Path

from main import app

OUT = Path(__file__).resolve().parent.parent / "documentation" / "openapi.json"


def main():
    schema = app.openapi()
    OUT.parent.mkdir(exist_ok=True)
    # sort_keys — чтобы дифф был стабильным и показывал только реальные изменения
    OUT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths = schema.get("paths", {})
    print(f"OpenAPI сохранён: {OUT}")
    print(f"Путей: {len(paths)}, версия схемы: {schema.get('openapi')}")


if __name__ == "__main__":
    main()
