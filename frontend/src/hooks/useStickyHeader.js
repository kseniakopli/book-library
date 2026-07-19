// Задача 50: компактная липкая шапка после прокрутки.
// Пороги РАЗНЫЕ (гистерезис): сжатие укорачивает страницу примерно на 60px,
// и с одним порогом состояние зацикливалось бы на границе.
import { useEffect, useState } from "react";

export function useStickyHeader() {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const onScroll = () =>
      setCompact((prev) => (prev ? window.scrollY > 8 : window.scrollY > 90));
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return compact;
}
