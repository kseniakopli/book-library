// Модалка «Найти книгу»: поиск во внешнем каталоге с debounce + добавление.
// Задача 18: после выбора кандидата — шаг с выбором статуса, а для
// «Прочитана» — дата прочтения с чекбоксом «Не помню».
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { STATUS_LABELS, STATUSES } from "../constants";
import { useFocusTrap } from "../hooks/useFocusTrap";

function SearchModal({ onClose }) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const modalRef = useRef(null);

  // Шаг 2 (задача 18): выбранный кандидат + статус + дата
  const [candidate, setCandidate] = useState(null);
  const [status, setStatus] = useState("want");
  const [readAt, setReadAt] = useState("");        // yyyy-mm-dd из <input type="date">
  const [dateUnknown, setDateUnknown] = useState(false);

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

  function pickCandidate(r) {
    setCandidate(r);
    setStatus("want");
    setReadAt("");
    setDateUnknown(false);
  }

  // Ручное добавление — каталог книгу не знает (частый случай для русских
  // изданий). Тот же шаг 2, но название и автор редактируются; название
  // предзаполняем из строки поиска.
  function pickManual() {
    pickCandidate({ manual: true, title: query.trim(), author: "" });
  }

  const manualIncomplete =
    candidate?.manual &&
    (!candidate.title.trim() || !candidate.author.trim());

  function submit() {
    // manual выкидываем из payload (в BookCreate его нет); префикс _ — сигнал
    // линтеру, что переменная намеренно не используется
    const { manual: _manual, ...book } = candidate;
    addBookMutation.mutate({
      ...book,
      title: book.title.trim(),
      author: book.author.trim(),
      status,
      read_at:
        status === "read" && !dateUnknown && readAt ? readAt : null,
    });
  }

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
          <h2 className="modal-title">
            {candidate ? "Добавить книгу" : "Найти книгу"}
          </h2>
          <button className="modal-close" onClick={onClose} aria-label="Закрыть">
            ×
          </button>
        </div>

        {candidate ? (
          <div className="add-form">
            {candidate.manual ? (
              <>
                <label className="field">
                  <span>Название</span>
                  <input
                    value={candidate.title}
                    onChange={(e) =>
                      setCandidate({ ...candidate, title: e.target.value })
                    }
                    autoFocus
                  />
                </label>
                <label className="field">
                  <span>Автор</span>
                  <input
                    value={candidate.author}
                    onChange={(e) =>
                      setCandidate({ ...candidate, author: e.target.value })
                    }
                  />
                </label>
              </>
            ) : (
              <>
                <p className="search-title">{candidate.title}</p>
                <p className="search-author">{candidate.author}</p>
              </>
            )}

            <div
              className="status-row add-status-row"
              role="group"
              aria-label="Статус книги"
            >
              {STATUSES.map((s) => (
                <button
                  key={s}
                  className={"pill " + (status === s ? "pill-active" : "")}
                  onClick={() => setStatus(s)}
                  aria-pressed={status === s}
                >
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>

            {status === "read" && (
              <div className="add-date-row">
                <label htmlFor="add-read-date">Дата прочтения:</label>
                <input
                  id="add-read-date"
                  type="date"
                  value={readAt}
                  onChange={(e) => setReadAt(e.target.value)}
                  disabled={dateUnknown}
                />
                <label className="add-date-unknown">
                  <input
                    type="checkbox"
                    checked={dateUnknown}
                    onChange={(e) => setDateUnknown(e.target.checked)}
                  />
                  Не помню
                </label>
              </div>
            )}

            {addBookMutation.isError && (
              <p className="error search-hint">
                Не удалось добавить книгу: {addBookMutation.error.message}
              </p>
            )}

            <div className="modal-actions">
              <button
                className="btn-ghost"
                onClick={() => setCandidate(null)}
                disabled={saving}
              >
                {candidate.manual ? "← К поиску" : "← К результатам"}
              </button>
              <button
                className="add-btn"
                onClick={submit}
                disabled={saving || manualIncomplete}
              >
                {saving ? "Добавляю…" : "Добавить"}
              </button>
            </div>
          </div>
        ) : (
          <>
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
                <p className="muted search-hint">
                  Ничего не найдено.{" "}
                  <button className="btn-ghost" onClick={pickManual}>
                    Добавить вручную
                  </button>
                </p>
              )}
            {searchError && (
              <p className="error search-hint">
                Поиск не удался. Попробуйте ещё раз.
              </p>
            )}

            <ul className="search-results">
              {searchResults.map((r, i) => (
                <li key={i}>
                  <button
                    className="search-item"
                    onClick={() => pickCandidate(r)}
                    disabled={r.on_shelf}
                  >
                    <span className="search-cover">
                      {r.cover_url && <img src={r.cover_url} alt="" />}
                    </span>
                    <span className="search-text">
                      <span className="search-title">
                        {r.title}
                        {/* книга уже в системе — атмосфера готова, добавление
                            переиспользует её; на полке — добавить нельзя */}
                        {r.on_shelf ? (
                          <span className="search-badge">уже у вас</span>
                        ) : (
                          r.source === "library" && (
                            <span className="search-badge">в каталоге</span>
                          )
                        )}
                      </span>
                      <span className="search-author">{r.author}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

export default SearchModal;
