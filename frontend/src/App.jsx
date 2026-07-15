import { useEffect, useRef, useState } from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import "./App.css";
import BookDetail from "./BookDetail";
import BookCard from "./BookCard";
import Shelf from "./Shelf";

// Страница книги: id из URL, книга из общего списка
function BookPage({ books, loading, onUpdated, onDeleted }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const book = books.find((b) => b.id === Number(id));

  if (loading) return <p className="muted">Загрузка…</p>;
  if (!book)
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
      onUpdated={onUpdated}
      onDeleted={onDeleted}
    />
  );
}

function App() {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const [filter, setFilter] = useState("");

  const [showModal, setShowModal] = useState(false);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  const [importMsg, setImportMsg] = useState("");
  const fileInputRef = useRef(null);
  const [shelfStart, setShelfStart] = useState({}); // позиция листания полок по названию

  const shelfProps = (title) => ({
    start: shelfStart[title] || 0,
    onStart: (v) => setShelfStart((prev) => ({ ...prev, [title]: v })),
  });

  useEffect(() => {
    fetch("/books")
      .then((r) => r.json())
      .then((data) => {
        setBooks(data);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 3) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    const timer = setTimeout(() => {
      fetch(`/search?q=${encodeURIComponent(term)}`)
        .then((r) => r.json())
        .then((data) => {
          setSearchResults(data.results);
          setSearching(false);
        });
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  async function addBook(candidate) {
    setSaving(true);
    const response = await fetch("/books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: candidate.title,
        author: candidate.author,
      }),
    });
    const newBook = await response.json();
    setBooks((prev) => [...prev, newBook]);
    setSaving(false);
    closeModal();
  }

  async function importCsv(e) {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/import", { method: "POST", body: formData });
    const data = await response.json();
    const fresh = await fetch("/books").then((r) => r.json());
    setBooks(fresh);
    setImportMsg(
      `Импортировано: ${data.imported}, дубликаты: ${data.duplicates ?? 0}, пропущено: ${data.skipped}`,
    );
    e.target.value = "";
  }

  function closeModal() {
    setShowModal(false);
    setQuery("");
    setSearchResults([]);
  }

  function handleUpdated(updated) {
    setBooks((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    // setSelectedBook больше не нужен: BookPage сам возьмёт свежую книгу из списка
  }

  function handleDeleted(id) {
    setBooks((prev) => prev.filter((b) => b.id !== id));
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
          >
            Импорт CSV
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
      {loading ? (
        <p className="muted">Загрузка…</p>
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
            {!searching && term.length >= 3 && searchResults.length === 0 && (
              <p className="muted search-hint">Ничего не найдено</p>
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
          element={
            <BookPage
              books={books}
              loading={loading}
              onUpdated={handleUpdated}
              onDeleted={handleDeleted}
            />
          }
        />
      </Routes>
    </div>
  );
}

export default App;
