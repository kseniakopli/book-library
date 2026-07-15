// Модалка «Найти книгу»: поиск во внешнем каталоге с debounce + добавление.
// Выделена из App.jsx (R6). Монтируется только когда открыта.
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useFocusTrap } from "../hooks/useFocusTrap";

function SearchModal({ onClose }) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const modalRef = useRef(null);

  useFocusTrap(modalRef, onClose);

  // Поиск: debounce 300 мс, затем useQuery — повтор того же запроса берётся из кэша
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
    queryKey: keys.search(debouncedTerm),
    queryFn: () => api.searchBooks(debouncedTerm),
    enabled: debouncedTerm.length >= 3, // не дёргать бэкенд, пока меньше 3 символов
  });
  const searchResults =
    debouncedTerm.length >= 3 ? (searchData?.results ?? []) : [];

  const addBookMutation = useMutation({
    mutationFn: api.createBook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      onClose();
    },
  });
  const saving = addBookMutation.isPending;

  const term = query.trim();

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Поиск и добавление книги"
        ref={modalRef}
      >
        <div className="modal-head">
          <h2 className="modal-title">Найти книгу</h2>
          <button className="modal-close" onClick={onClose} aria-label="Закрыть">
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
                onClick={() => addBookMutation.mutate(r)}
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
  );
}

export default SearchModal;
