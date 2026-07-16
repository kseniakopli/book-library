// Главная: шапка с темой и импортом, поиск по библиотеке, полки.
// Выделена из App.jsx (R6).
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useTheme } from "../hooks/useTheme";
import BookCard from "../components/BookCard";
import Shelf from "../components/Shelf";
import SearchModal from "../components/SearchModal";

function HomePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  const [filter, setFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [importMsg, setImportMsg] = useState("");
  const fileInputRef = useRef(null);
  const addButtonRef = useRef(null);
  // Позиция полок: HomePage размонтируется при уходе на карточку книги,
  // поэтому state не выживает — храним в sessionStorage (переживает возврат и F5,
  // чистится при закрытии вкладки)
  const [shelfStart, setShelfStart] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem("shelfStart")) || {};
    } catch {
      return {};
    }
  });
  useEffect(() => {
    sessionStorage.setItem("shelfStart", JSON.stringify(shelfStart));
  }, [shelfStart]);

  const shelfProps = (title) => ({
    start: shelfStart[title] || 0,
    onStart: (v) => setShelfStart((prev) => ({ ...prev, [title]: v })),
  });

  // Задача 50: компактная липкая шапка после прокрутки
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Список книг: кэш keys.books; пока есть pending — поллинг каждые 2 секунды
  const {
    data: books = [],
    isLoading: loading,
    isError: booksError,
    refetch: refetchBooks,
  } = useQuery({
    queryKey: keys.books,
    queryFn: api.getBooks,
    refetchInterval: (q) =>
      q.state.data?.some((b) => b.enrich_status === "pending") ? 2000 : false,
  });

  const importMutation = useMutation({
    mutationFn: api.importCsv,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      setImportMsg(
        `Импортировано: ${data.imported}, дубликаты: ${data.duplicates ?? 0}, пропущено: ${data.skipped}`,
      );
    },
  });

  function importCsv(e) {
    const file = e.target.files[0];
    if (!file) return;
    importMutation.mutate(file);
    e.target.value = "";
  }

  function closeModal() {
    setShowModal(false);
    addButtonRef.current?.focus(); // вернуть фокус туда, откуда открывали
  }

  const openBook = (b) => navigate(`/books/${b.id}`);

  const trimmed = filter.trim().toLowerCase();
  const filtered = trimmed
    ? books.filter(
        (b) =>
          b.title.toLowerCase().includes(trimmed) ||
          b.author.toLowerCase().includes(trimmed),
      )
    : null;
  const readBooks = books.filter((b) => b.status === "read");
  const wantBooks = books.filter((b) => b.status === "want");

  return (
    <>
      <header className={"header" + (scrolled ? " header-compact" : "")}>
        <div>
          <h1 className="title">Библиотека</h1>
          <p className="subtitle">Атмосферные литературные вечера</p>
        </div>
        <div className="header-actions">
          <button
            className="btn-ghost theme-toggle"
            onClick={toggleTheme}
            aria-pressed={theme === "dark"}
            aria-label={
              theme === "dark"
                ? "Включить светлую тему"
                : "Включить вечернюю тему"
            }
            title={theme === "dark" ? "Светлая тема" : "Вечерняя тема"}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <input
            type="file"
            accept=".csv"
            ref={fileInputRef}
            onChange={importCsv}
            className="file-input-hidden"
            aria-label="Файл CSV для импорта"
          />
          <button
            className="btn-ghost"
            onClick={() => fileInputRef.current.click()}
            disabled={importMutation.isPending}
          >
            {importMutation.isPending ? "Импортирую…" : "Импорт CSV"}
          </button>
          <button
            className="add-btn"
            onClick={() => setShowModal(true)}
            ref={addButtonRef}
          >
            + Добавить книгу
          </button>
        </div>
      </header>

      <input
        className="lib-search"
        placeholder="Поиск по библиотеке…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />

      {importMsg && <p className="muted">{importMsg}</p>}
      {importMutation.isError && (
        <p className="error">
          Импорт не удался: {importMutation.error.message}
        </p>
      )}

      {loading ? (
        <p className="muted">Загрузка…</p>
      ) : booksError ? (
        <p className="error">
          Не удалось загрузить библиотеку.{" "}
          <button className="btn-ghost" onClick={() => refetchBooks()}>
            Повторить
          </button>
        </p>
      ) : filtered ? (
        filtered.length === 0 ? (
          <p className="muted">Ничего не найдено в библиотеке.</p>
        ) : (
          <div className="grid">
            {filtered.map((book) => (
              <BookCard key={book.id} book={book} onSelect={openBook} />
            ))}
          </div>
        )
      ) : (
        <>
          <Shelf
            title="Прочитано"
            books={readBooks}
            onSelect={openBook}
            {...shelfProps("Прочитано")}
          />
          <Shelf
            title="Хочу прочитать"
            books={wantBooks}
            onSelect={openBook}
            {...shelfProps("Хочу прочитать")}
          />
          <Shelf
            title="Рекомендации"
            placeholder="Скоро — на основе прочитанного"
          />
        </>
      )}

      {showModal && <SearchModal onClose={closeModal} />}
    </>
  );
}

export default HomePage;
