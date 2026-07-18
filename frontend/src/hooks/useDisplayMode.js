// Режим отображения полки (задача 66): "covers" — реальные обложки,
// "symbols" — экслибрис на палитре паспорта для всех книг (единый вид nocturne).
// Сохраняется в localStorage, как тема. На этапе 9 переедет в личный кабинет.
import { useEffect, useState } from "react";

export function useDisplayMode() {
  const [mode, setMode] = useState(
    () => localStorage.getItem("displayMode") || "covers",
  );

  useEffect(() => {
    localStorage.setItem("displayMode", mode);
  }, [mode]);

  const toggleMode = () =>
    setMode((m) => (m === "symbols" ? "covers" : "symbols"));

  return { mode, toggleMode };
}
