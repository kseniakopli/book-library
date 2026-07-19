// Корень приложения: только маршруты (R6).
// Страницы — в pages/, переиспользуемые блоки — в components/.
import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import "./App.css";
import { useTheme } from "./hooks/useTheme";
import HomePage from "./pages/HomePage";
import BookPage from "./pages/BookPage";

// Задача 56б: печатная карточка и сцена «вечера» — тяжёлые и редко открываемые,
// грузим их отдельными чанками по требованию (React.lazy → меньше стартовый бандл).
const CardPage = lazy(() => import("./pages/CardPage"));
const EveningPage = lazy(() => import("./pages/EveningPage"));

function App() {
  // Применяем сохранённую тему на уровне App: он смонтирован всегда,
  // поэтому F5 на любой странице (включая /books/N) не теряет тему.
  // Переключатель остаётся в HomePage — оба хука читают один localStorage.
  useTheme();
  return (
    <div className="app">
      <Suspense fallback={<p className="muted">Загрузка…</p>}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/books/:id" element={<BookPage />} />
          <Route path="/books/:id/card" element={<CardPage />} />
          <Route path="/books/:id/evening" element={<EveningPage />} />
        </Routes>
      </Suspense>
    </div>
  );
}

export default App;
