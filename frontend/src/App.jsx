// Корень приложения: только маршруты (R6).
// Страницы — в pages/, переиспользуемые блоки — в components/.
import { Route, Routes } from "react-router-dom";
import "./App.css";
import HomePage from "./pages/HomePage";
import BookPage from "./pages/BookPage";
import CardPage from "./pages/CardPage";

function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/books/:id" element={<BookPage />} />
        <Route path="/books/:id/card" element={<CardPage />} />
      </Routes>
    </div>
  );
}

export default App;
