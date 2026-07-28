// Корень приложения: публичная витрина, авторизация (этап 9) и маршруты (R6).
// Страницы — в pages/, переиспользуемые блоки — в components/.
import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import "./App.css";
import { useTheme } from "./hooks/useTheme";
import { useAuth } from "./hooks/useAuth";
import HomePage from "./pages/HomePage";
import BookPage from "./pages/BookPage";
import LoginPage from "./pages/LoginPage";

// Задача 56б: печатная карточка и сцена «вечера» — тяжёлые и редко открываемые,
// грузим их отдельными чанками по требованию (React.lazy → меньше стартовый бандл).
const CardPage = lazy(() => import("./pages/CardPage"));
const EveningPage = lazy(() => import("./pages/EveningPage"));
// Статистика (задачи 24/63) тянет recharts — самый тяжёлый пакет в проекте.
const StatsPage = lazy(() => import("./pages/StatsPage"));
// Циклы (задача 89) — отдельный экран, открывается не каждую сессию
const SeriesPage = lazy(() => import("./pages/SeriesPage"));
// Задача 30: публичная витрина — её открывают ГОСТИ, поэтому она тоже отдельным
// чанком: владельцу сервиса этот код в бандле не нужен, и наоборот.
const ShowcasePage = lazy(() => import("./pages/ShowcasePage"));
const ShowcaseBookPage = lazy(() => import("./pages/ShowcaseBookPage"));

// Ворота авторизации. Оборачивают только приватные страницы — на витрине
// useAuth не вызывается вовсе, и гость не делает лишний запрос /auth/me.
function RequireAuth({ children }) {
  const { user, loading, failed } = useAuth();

  // пока «кто я» в пути — ничего не рисуем, иначе мелькнёт то вход, то чужой UI
  if (loading) return <p className="muted">Загрузка…</p>;
  if (failed) {
    return <p className="error">Сервис недоступен. Попробуйте обновить страницу.</p>;
  }
  if (!user) return <LoginPage />;
  return children;
}

function App() {
  // Применяем сохранённую тему на уровне App: он смонтирован всегда,
  // поэтому F5 на любой странице (включая /books/N) не теряет тему.
  useTheme();

  return (
    <div className="app">
      <Suspense fallback={<p className="muted">Загрузка…</p>}>
        <Routes>
          {/* --- открыто без входа (задача 30) --- */}
          <Route path="/u/:slug" element={<ShowcasePage />} />
          <Route path="/u/:slug/books/:id" element={<ShowcaseBookPage />} />

          {/* --- всё остальное только для вошедших --- */}
          <Route
            path="/"
            element={
              <RequireAuth>
                <HomePage />
              </RequireAuth>
            }
          />
          <Route
            path="/books/:id"
            element={
              <RequireAuth>
                <BookPage />
              </RequireAuth>
            }
          />
          <Route
            path="/books/:id/card"
            element={
              <RequireAuth>
                <CardPage />
              </RequireAuth>
            }
          />
          <Route
            path="/books/:id/evening"
            element={
              <RequireAuth>
                <EveningPage />
              </RequireAuth>
            }
          />
          <Route
            path="/stats"
            element={
              <RequireAuth>
                <StatsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/series/:id"
            element={
              <RequireAuth>
                <SeriesPage />
              </RequireAuth>
            }
          />
          {/* вошёл, а адрес /login — показываем библиотеку */}
          <Route
            path="/login"
            element={
              <RequireAuth>
                <HomePage />
              </RequireAuth>
            }
          />
        </Routes>
      </Suspense>
    </div>
  );
}

export default App;
