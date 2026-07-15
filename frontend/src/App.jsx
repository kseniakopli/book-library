import { useEffect, useRef, useState } from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import "./App.css";
import BookDetail from "./BookDetail";
import BookCard from "./BookCard";
import Shelf from "./Shelf";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";

// Страница книги: id из URL, книга из общего списка
function BookPage({ onDeleted }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    data: book,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["books", Number(id)],
    queryFn: () => api.getBook(id),
    refetchInterval: (q) =>
      q.state.data?.enrich_status === "pending" ? 2000 : false,
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError || !book)
    return (
      <div>
        <p className="muted">Книга не найдена.</p>
        <button className="btn-ghost" onClick={() => navigate("/")}>
          ← К библиотеке
        </button>
      </div>
    );

  return (
    <BookDetail
      book={book}
      onBack={() => navigate("/")}
      onDeleted={onDeleted}
    />
  );
}

function App() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [filter, setFilter] = useState("");

  const [showModal, setShowModal] = useState(false);
  const [query, setQuery] = useState("");

  const [importMsg, setImportMsg] = useState("");
  const fileInputRef = useRef(null);
  const [shelfStart, setShelfStart] = useState({}); // позиция листания полок по названию

  const shelfProps = (title) => ({
    start: shelfStart[title] || 0,
    onStart: (v) => setShelfStart((prev) => ({ ...prev, [title]: v })),
  });

  // Список книг: кэш под ключом ["books"], загрузка и обновление — забота React Query
  const {
    data: books = [],
    isLoading: loading,
    isError: booksError,
    refetch: refetchBooks,
  } = useQuery({
    queryKey: ["books"],
    queryFn: api.getBooks,
    // пока есть книги со статусом pending — опрашиваем список каждые 2 секунды
    refetchInterval: (q) =>
      q.state.data?.some((b) => b.enrich_status === "pending") ? 2000 : false,
  });

  // Поиск: debounce оставляем, а сам запрос — через useQuery.
  // Повторный ввод того же запроса возьмётся из кэша без похода в сеть.
  const [debouncedTerm, setDebouncedTerm] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedTerm(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const {
    data: searchData,
    isFetching: searching,
    isError: searchError,
  } = useQuery({
    queryKey: ["search", debouncedTerm],
    queryFn: () => api.searchBooks(debouncedTerm),
    enabled: debouncedTerm.length >= 3, // не дёргать бэкенд, пока меньше 3 символов
  });
  const searchResults =
    debouncedTerm.length >= 3 ? (searchData?.results ?? []) : [];

  // Мутации: после успеха инвалидируем кэш — список перезапросится сам
  const addBookMutation = useMutation({
    mutationFn: api.createBook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["books"] });
      closeModal();
    },
  });
  const saving = addBookMutation.isPending;

  const importMutation = useMutation({
    mutationFn: api.importCsv,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["books"] });
      setImportMsg(
        `Импортировано: ${data.imported}, дубликаты: ${data.duplicates ?? 0}, пропущено: ${data.skipped}`,
      );
    },
  });

  function addBook(candidate) {
    addBookMutation.mutate(candidate);
  }

  function importCsv(e) {
    const file = e.target.files[0];
    if (!file) return;
    importMutation.mutate(file);
    e.target.value = "";
  }

  function closeModal() {
    setShowModal(false);
    setQuery("");
  }

  function handleDeleted() {
    queryClient.invalidateQueries({ queryKey: ["books"] });
    navigate("/");
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
  const term = query.trim();

  const home = (
    <>
      <header className="header">
        <div>
          <h1 className="title">Библиотека</h1>
          <p className="subtitle">Атмосферные литературные вечера</p>
        </div>
        <div className="header-actions">
          <input
            type="file"
            accept=".csv"
            ref={fileInputRef}
            onChange={importCsv}
            style={{ display: "none" }}
          />
          <button
            className="btn-ghost"
            onClick={() => fileInputRef.current.click()}
            disabled={importMutation.isPending}
          >
            {importMutation.isPending ? "Импортирую…" : "Импорт CSV"}
          </button>
          <button className="add-btn" onClick={() => setShowModal(true)}>
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
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h2 className="modal-title">Найти книгу</h2>
              <button
                className="modal-close"
                onClick={closeModal}
                aria-label="Закрыть"
              >
                ×
              </button>
            </div>
            <input
              className="search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Название или автор…"
              autoFocus
            />

            {term.length > 0 && term.length < 3 && (
              <p className="muted search-hint">Введите хотя бы 3 символа</p>
            )}
            {searching && <p className="muted search-hint">Ищу…</p>}
            {!searchError &&
              !searching &&
              term.length >= 3 &&
              searchResults.length === 0 && (
                <p className="muted search-hint">Ничего не найдено</p>
              )}
            {searchError && (
              <p className="error search-hint">
                Поиск не удался. Попробуйте ещё раз.
              </p>
            )}
            {addBookMutation.isError && (
              <p className="error search-hint">
                Не удалось добавить книгу: {addBookMutation.error.message}
              </p>
            )}

            <ul className="search-results">
              {searchResults.map((r, i) => (
                <li key={i}>
                  <button
                    className="search-item"
                    onClick={() => addBook(r)}
                    disabled={saving}
                  >
                    <span className="search-cover">
                      {r.cover_url && <img src={r.cover_url} alt="" />}
                    </span>
                    <span className="search-text">
                      <span className="search-title">{r.title}</span>
                      <span className="search-author">{r.author}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );

  return (
    <div className="app">
      <Routes>
        <Route path="/" element={home} />
        <Route
          path="/books/:id"
          element={<BookPage onDeleted={handleDeleted} />}
        />
      </Routes>
    </div>
  );
}

export default App;
