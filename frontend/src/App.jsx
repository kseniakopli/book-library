import { useEffect, useState } from "react";
import "./App.css";
import BookDetail from "./BookDetail";

const STATUS_LABELS = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

function App() {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedBook, setSelectedBook] = useState(null);

  const [showModal, setShowModal] = useState(false);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/books")
      .then((r) => r.json())
      .then((data) => {
        setBooks(data);
        setLoading(false);
      });
  }, []);

  // Поиск с дебаунсом: ждём паузу в наборе, чтобы не дёргать сервер на каждый символ
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
    return () => clearTimeout(timer);   // новый ввод отменяет предыдущий таймер
  }, [query]);

  async function addBook(candidate) {
    setSaving(true);
    const response = await fetch("/books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: candidate.title, author: candidate.author }),
    });
    const newBook = await response.json();
    setBooks((prev) => [...prev, newBook]);
    setSaving(false);
    closeModal();
  }

  function closeModal() {
    setShowModal(false);
    setQuery("");
    setSearchResults([]);
  }

  function handleUpdated(updated) {
    setBooks((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    setSelectedBook(updated);
  }

  if (selectedBook) {
    return (
      <div className="app">
        <BookDetail
          book={selectedBook}
          onBack={() => setSelectedBook(null)}
          onUpdated={handleUpdated}
        />
      </div>
    );
  }

  const term = query.trim();

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1 className="title">Библиотека</h1>
          <p className="subtitle">Атмосферные литературные вечера</p>
        </div>
        <button className="add-btn" onClick={() => setShowModal(true)}>
          + Добавить книгу
        </button>
      </header>

      {loading ? (
        <p className="muted">Загрузка…</p>
      ) : books.length === 0 ? (
        <p className="muted">Пока нет книг. Добавьте первую.</p>
      ) : (
        <div className="grid">
          {books.map((book) => (
            <article className="book" key={book.id} onClick={() => setSelectedBook(book)}>
              <div className="cover">
                {book.cover_url ? (
                  <img src={book.cover_url} alt={book.title} />
                ) : (
                  <div className="cover-empty">Нет обложки</div>
                )}
              </div>
              <h2 className="book-title">{book.title}</h2>
              <p className="book-author">{book.author}</p>
              <div className="book-meta">
                <span className="status">{STATUS_LABELS[book.status]}</span>
                {book.status === "read" && book.rating != null && (
                  <span className="rating">★ {book.rating}/10</span>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-head">
              <h2 className="modal-title">Найти книгу</h2>
              <button className="modal-close" onClick={closeModal} aria-label="Закрыть">×</button>
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
                  <button className="search-item" onClick={() => addBook(r)} disabled={saving}>
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
    </div>
  );
}

export default App;