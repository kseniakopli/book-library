// Корень приложения: только маршруты (R6).
// Страницы — в pages/, переиспользуемые блоки — в components/.
import { Route, Routes } from "react-router-dom";
import "./App.css";
import { useTheme } from "./hooks/useTheme";
import HomePage from "./pages/HomePage";
import BookPage from "./pages/BookPage";
import CardPage from "./pages/CardPage";
import EveningPage from "./pages/EveningPage";

function App() {
  // Применяем сохранённую тему на уровне App: он смонтирован всегда,
  // поэтому F5 на любой странице (включая /books/N) не теряет тему.
  // Переключатель остаётся в HomePage — оба хука читают один localStorage.
  useTheme();
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/books/:id" element={<BookPage />} />
        <Route path="/books/:id/card" element={<CardPage />} />
        <Route path="/books/:id/evening" element={<EveningPage />} />
      </Routes>
    </div>
  );
}

export default App;
