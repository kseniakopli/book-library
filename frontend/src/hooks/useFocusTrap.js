// Доступность модалок (задача 23): Esc закрывает, Tab не выпускает фокус наружу.
// Вешать на контейнер, который смонтирован только пока модалка открыта.
import { useEffect } from "react";

export function useFocusTrap(ref, onEscape) {
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape") {
        onEscape();
        return;
      }
      if (e.key !== "Tab" || !ref.current) return;
      const focusables = ref.current.querySelectorAll(
        "button:not(:disabled), input, select",
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [ref, onEscape]);
}
