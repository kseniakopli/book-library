"""Обложка Spotify-плейлиста из символа-экслибриса книги (20.07).

Spotify принимает ТОЛЬКО base64-JPEG размером до 256 КБ, а символ у нас —
SVG. Здесь вектор растрируется и кладётся по центру квадрата на фон палитры
паспорта. Текста на обложке нет сознательно: в сетке плейлистов картинка
мелкая, надпись всё равно не читается, а символ узнаётся.

Растеризация — svglib + reportlab: чистые python-колёса, ставятся на Windows
без системных библиотек (в отличие от cairosvg с его Cairo). Понимают
подмножество SVG (path/circle/rect/line/polygon) — ровно то, что мы просим
у модели в промпте паспорта.

Функция никогда не бросает: обложка — украшение, плейлист важнее.
"""

import base64
import io
import json
import logging
import re

log = logging.getLogger("nocturne")

SIZE = 640            # квадрат обложки (Spotify показывает и мельче)
SYMBOL_RATIO = 0.62   # доля стороны под символ — вокруг остаются поля
MAX_BASE64 = 256 * 1024
DEFAULT_BG = "#161311"


VIEWBOX = re.compile(r"""viewBox\s*=\s*["']([-\d.\s,]+)["']""", re.I)


def _normalize(svg: str, background: str) -> str:
    """Готовим SVG к растеризации:
    1) width/height — модель отдаёт `<svg viewBox="0 0 100 100">` без них,
       а svglib в этом случае считает размер нулевым и рисовать отказывается
       (именно на этом обложка не собиралась при первом прогоне 20.07);
    2) xmlns — без пространства имён парсер молча вернёт пустой рисунок;
    3) фоновый прямоугольник — символ рисуется на прозрачном фоне, который
       при растеризации стал бы чёрным.
    """
    width = height = 100.0
    box = VIEWBOX.search(svg)
    if box:
        parts = box.group(1).replace(",", " ").split()
        if len(parts) == 4:
            try:
                width, height = float(parts[2]), float(parts[3])
            except ValueError:
                pass

    if not re.search(r"<svg[^>]*\swidth\s*=", svg, re.I):
        svg = re.sub(
            r"<svg", f'<svg width="{width}" height="{height}"', svg, count=1
        )
    if "xmlns" not in svg[:200]:
        svg = re.sub(r"<svg", '<svg xmlns="http://www.w3.org/2000/svg"', svg, count=1)

    rect = f'<rect width="100%" height="100%" fill="{background}"/>'
    return re.sub(r"(<svg[^>]*>)", lambda m: m.group(1) + rect, svg, count=1)


def rasterizer_available() -> bool:
    """Есть ли рабочий растеризатор. reportlab 4 рисует через бэкенд rlPyCairo:
    без него renderPM бросает «cannot import desired renderPM backend rlPyCairo».
    Используется тестами (чтобы не падать там, где библиотек нет) и для
    диагностики: `python -c "from services.cover_art import rasterizer_available;
    print(rasterizer_available())"`."""
    try:
        from reportlab.graphics import renderPM
        from reportlab.graphics.shapes import Drawing

        renderPM.drawToPIL(Drawing(4, 4))
        return True
    except Exception:
        return False


def _render_svg(svg: str, box: int):
    """SVG → PIL.Image заданного размера. None, если растеризатора нет
    или SVG не по зубам библиотеке."""
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg
    except ImportError:
        log.info("обложка плейлиста: svglib/reportlab не установлены — пропускаю")
        return None

    try:
        drawing = svg2rlg(io.BytesIO(svg.encode("utf-8")))
        if drawing is None:
            log.warning("обложка плейлиста: svglib не разобрал символ")
            return None
        if not drawing.width or not drawing.height:
            log.warning("обложка плейлиста: нулевой размер рисунка")
            return None
        scale = box / max(drawing.width, drawing.height)
        drawing.width *= scale
        drawing.height *= scale
        drawing.scale(scale, scale)
        return renderPM.drawToPIL(drawing)
    except Exception as e:
        log.warning("обложка плейлиста: не удалось растрировать символ: %s", e)
        return None


def build_cover(design_payload: str) -> str | None:
    """base64-JPEG обложки по сохранённому паспорту оформления книги
    (`AISelection.payload` категории design). None — если не вышло."""
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        design = json.loads(design_payload)
    except (TypeError, ValueError):
        return None

    svg = design.get("symbol_svg")
    if not svg:
        return None
    # старый формат паспорта — одно поле palette
    palette = design.get("palette_dark") or design.get("palette") or {}
    background = palette.get("bg", DEFAULT_BG)

    symbol = _render_svg(_normalize(svg, background), int(SIZE * SYMBOL_RATIO))
    if symbol is None:
        return None

    canvas = Image.new("RGB", (SIZE, SIZE), background)
    offset = ((SIZE - symbol.width) // 2, (SIZE - symbol.height) // 2)
    canvas.paste(symbol, offset)

    # ужимаем, пока не влезем в лимит Spotify (обычно хватает первой итерации)
    for quality in (90, 75, 60, 45):
        buffer = io.BytesIO()
        canvas.save(buffer, format="JPEG", quality=quality, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        if len(encoded) <= MAX_BASE64:
            return encoded
    log.warning("обложка плейлиста: не удалось уложиться в 256 КБ")
    return None
