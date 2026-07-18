// Скелетоны-заглушки на время загрузки (задача 67): янтарный shimmer в тон
// бренду вместо текстовых лоадеров. Форма повторяет будущий контент.

// Несколько строк-«треков» — для музыкальной подборки и списков еды/ароматов.
export function SkeletonRows({ rows = 4 }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton-row" key={i}>
          <span className="skeleton skeleton-line" style={{ width: "45%" }} />
          <span className="skeleton skeleton-line" style={{ width: "25%" }} />
        </div>
      ))}
    </div>
  );
}

// Несколько строк текста разной длины — для пояснения/паспорта оформления.
export function SkeletonText({ lines = 3 }) {
  const widths = ["92%", "80%", "60%", "70%", "50%"];
  return (
    <div aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <span
          className="skeleton skeleton-line"
          key={i}
          style={{ width: widths[i % widths.length] }}
        />
      ))}
    </div>
  );
}
