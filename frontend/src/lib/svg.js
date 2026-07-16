// SVG символа → data-URI для <img> (скрипты внутри <img> не исполняются).
// Браузер требует xmlns у standalone-SVG — добавляем, если AI его опустил.
export function svgDataUri(svg) {
  const withNs = svg.includes("xmlns=")
    ? svg
    : svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
  return `data:image/svg+xml;utf8,${encodeURIComponent(withNs)}`;
}
