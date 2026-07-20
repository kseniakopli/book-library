"""Разовый скрипт: генерирует статичный QR со ссылкой на лендинг.

Результат — frontend/public/landing-qr.svg (вектор, идеально резкий на печати).
Используется в подвале оборота печатной карточки (CardPage).

Запуск из папки backend/:
    python make_landing_qr.py

Перегенерировать нужно только если сменится адрес лендинга (свой домен).
"""

from pathlib import Path

import qrcode
import qrcode.image.svg

LANDING_URL = "https://nocturne-library.netlify.app/"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "landing-qr.svg"

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
