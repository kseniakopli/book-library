"""Разовый скрипт: генерирует статичный QR для подвала печатной карточки.

Результат — frontend/public/landing-qr.svg (вектор, идеально резкий на печати).
Используется в подвале оборота печатной карточки (CardPage).

⚠ 26.07: QR ведёт на ПУБЛИЧНУЮ ВИТРИНУ (задача 30), а не на лендинг.
Решение Ксении: сервис работает, и звать человека с бумажной карточки на
страницу «оставьте почту» бессмысленно — пусть сразу видит отобранные книги
с их атмосферой. Лендинг остаётся отдельно, для листа ожидания.

Запуск из папки backend/:
    python scripts/make_landing_qr.py
    python scripts/make_landing_qr.py https://другой-адрес/   — свой URL

Перегенерировать нужно, если сменится слаг витрины или домен.
"""

import sys
from pathlib import Path

import qrcode
import qrcode.image.svg

# ⚠ Имя «landing» ИСТОРИЧЕСКОЕ. Лендинга больше нет (удалён 01.08: его роль
# играет публичная витрина), а QR ведёт на витрину ещё с 28.07. Файл и скрипт
# не переименованы сознательно: путь /landing-qr.svg зашит в печатную карточку,
# и трогать её ради косметики — лишний риск.
#
# слаг задаётся scripts/set_showcase.py — адрес должен совпадать с ним
# 28.07: ksenia → publiclib (витрина обезличена, отсылок к владельцу нет)
DEFAULT_URL = "https://nocturne-library.fly.dev/u/publiclib"
LANDING_URL = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
OUT = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "landing-qr.svg"

qr = qrcode.QRCode(
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    border=3,  # quiet zone — обязательна для уверенного сканирования с бумаги
)
qr.add_data(LANDING_URL)
qr.make(fit=True)
# SvgPathFillImage — чёрные модули на белом фоне, один <path>
img = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage)
img.save(str(OUT))
print(f"QR для {LANDING_URL}")
print(f"Записан: {OUT} ({qr.modules_count}×{qr.modules_count} модулей)")
print("⚠ Проверьте телефоном перед печатью тиража.")
