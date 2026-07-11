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
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/books")
      .then((r) => r.json())
      .then((data) => {
        setBooks(data);
        setLoading(false);
      });
  }, []);

  async function addBook(e) {
    e.preventDefault();
    if (!title || !author) return;
    setSaving(true);
    const response = await fetch("/books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, author }),
    });
    const newBook = await response.json();
    setBooks((prev) => [...prev, newBook]);
    setSaving(false);
    setTitle("");
    setAuthor("");
    setShowModal(false);
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
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Новая книга</h2>
            <form onSubmit={addBook}>
              <label className="field">
                <span>Название</span>
                <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
              </label>
              <label className="field">
                <span>Автор</span>
                <input value={author} onChange={(e) => setAuthor(e.target.value)} />
              </label>
              <div className="modal-actions">
                <button type="button" className="btn-ghost" onClick={() => setShowModal(false)}>
                  Отмена
                </button>
                <button type="submit" className="add-btn" disabled={saving}>
                  {saving ? "Добавляю…" : "Добавить"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;