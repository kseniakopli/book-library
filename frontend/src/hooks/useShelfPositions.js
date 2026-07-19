// Позиция листания полок (ревью 19.07 — вынесено из HomePage).
//
// HomePage размонтируется при уходе на страницу книги, поэтому обычный state
// не выживает. Храним в sessionStorage: переживает возврат и F5, чистится при
// закрытии вкладки. Возвращает функцию, дающую пропсы конкретной полке.
import { useEffect, useState } from "react";

const STORAGE_KEY = "shelfStart";

export function useShelfPositions() {
  const [starts, setStarts] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(starts));
  }, [starts]);

  return (title) => ({
    start: starts[title] || 0,
    onStart: (value) => setStarts((prev) => ({ ...prev, [title]: value })),
  });
}
