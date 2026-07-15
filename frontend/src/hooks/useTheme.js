// Тема light/dark (задача 22): атрибут на <html> + сохранение в localStorage.
import { useEffect, useState } from "react";

export function useTheme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || "light",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme; // включает [data-theme="dark"] в tokens.css
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return { theme, toggleTheme };
}
