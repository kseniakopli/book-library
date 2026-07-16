// Работа с SVG символа-экслибриса.
// Безопасность: SVG проверен на бэкенде (нет script/обработчиков/ссылок),
// рендер всегда через <img data:> — там скрипты не исполняются в принципе.

export function svgDataUri(svg) {
  const withNs = svg.includes("xmlns=")
    ? svg
    : svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
  return `data:image/svg+xml;utf8,${encodeURIComponent(withNs)}`;
}

// AI часто рисует символ не по центру своего viewBox — CSS это не лечит
// (object-fit центрирует холст, а не рисунок). Меряем реальные границы
// рисунка (getBBox) и перецентровываем viewBox по ним с небольшими полями.
export function centeredSvgDataUri(svg) {
  try {
    const withNs = svg.includes("xmlns=")
      ? svg
      : svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
    const doc = new DOMParser().parseFromString(withNs, "image/svg+xml");
    const el = doc.documentElement;
    if (el.tagName.toLowerCase() !== "svg") return svgDataUri(svg);

    // getBBox работает только у элемента в DOM — вставляем невидимо и убираем
    el.style.position = "absolute";
    el.style.opacity = "0";
    el.style.pointerEvents = "none";
    document.body.appendChild(el);
    const box = el.getBBox();
    document.body.removeChild(el);
    el.removeAttribute("style");

    if (box.width > 0 && box.height > 0) {
      // квадратный кадр по большей стороне + поля 10% —
      // символ центрирован и не прилипает к рамке
      const side = Math.max(box.width, box.height);
      const pad = side * 0.1;
      const cx = box.x + box.width / 2;
      const cy = box.y + box.height / 2;
      const half = side / 2 + pad;
      el.setAttribute(
        "viewBox",
        `${cx - half} ${cy - half} ${half * 2} ${half * 2}`,
      );
      el.removeAttribute("width");
      el.removeAttribute("height");
    }
    return `data:image/svg+xml;utf8,${encodeURIComponent(
      new XMLSerializer().serializeToString(el),
    )}`;
  } catch {
    return svgDataUri(svg);   // не смогли разобрать — показываем как есть
  }
}
