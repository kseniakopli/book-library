// Жанры книги (задача 112): показ ссылками, правка — у админа.
//
// Жанры ОБЩИЕ: книга одна на всю базу, её жанры видят все читатели. Поэтому
// правка admin-only — то же основание, что у полей книги.
//
// ⚠ Ввод свободный, с подсказками из уже заведённых жанров. Выпадающий список
// «выбери из существующих» не годится: первые жанры заводить было бы неоткуда,
// а строгий справочник для двух сотен книг — это отдельный экран
// администрирования, которого никто не просил.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useAuth } from "../hooks/useAuth";

const MAX_GENRES = 5;

/** Рубрики Google Books — подсказка админу, а не жанры (решение Ксении 03.08).
 *  «Fiction / General» одинаково у половины библиотеки, поэтому в промпт
 *  они больше не уезжают, но при заполнении иногда напоминают, что за книга. */
function categoriesHint(raw) {
  try {
    const list = JSON.parse(raw || "[]");
    return Array.isArray(list) ? list.slice(0, 3).join(", ") : "";
  } catch {
    return "";
  }
}

function BookGenres({ bookId, genres = [], categories }) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(genres.map((g) => g.name));
  const [input, setInput] = useState("");

  // подсказки: уже заведённые жанры библиотеки
  const known = useQuery({
    queryKey: keys.genres,
    queryFn: api.getGenres,
    enabled: editing,          // список нужен только в режиме правки
  });

  const save = useMutation({
    mutationFn: () => api.setBookGenres(bookId, draft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.book(bookId) });
      queryClient.invalidateQueries({ queryKey: keys.genres });
      setEditing(false);
    },
  });

  function addGenre(name) {
    const clean = name.trim();
    if (!clean || draft.length >= MAX_GENRES) return;
    // сравниваем без регистра — иначе «Детектив» и «детектив» станут двумя
    if (draft.some((g) => g.toLowerCase() === clean.toLowerCase())) return;
    setDraft([...draft, clean]);
    setInput("");
  }

  if (!editing) {
    if (genres.length === 0 && !isAdmin) return null;
    return (
      <div className="book-genres">
        {genres.length > 0 ? (
          <ul className="book-genres-list">
            {genres.map((genre) => (
              <li key={genre.id}>
                <Link className="pill" to={`/genres/${genre.id}`}>
                  {genre.name}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <span className="muted">Жанры не проставлены</span>
        )}
        {isAdmin && (
          <button className="btn-ghost book-genres-edit" onClick={() => setEditing(true)}>
            {genres.length ? "Изменить жанры" : "Проставить жанры"}
          </button>
        )}
      </div>
    );
  }

  const hint = categoriesHint(categories);
  const suggestions = (known.data?.genres ?? [])
    .filter((g) => !draft.some((d) => d.toLowerCase() === g.name.toLowerCase()))
    .slice(0, 8);

  return (
    <div className="book-genres book-genres-editing">
      <ul className="book-genres-list">
        {draft.map((name) => (
          <li key={name}>
            <span className="pill pill-active">
              {name}
              <button
                className="book-genres-remove"
                onClick={() => setDraft(draft.filter((g) => g !== name))}
                aria-label={`Убрать жанр ${name}`}
              >
                ×
              </button>
            </span>
          </li>
        ))}
      </ul>

      {draft.length < MAX_GENRES && (
        <div className="book-genres-input-row">
          <input
            className="book-genres-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();   // иначе сабмит формы правки книги
                addGenre(input);
              }
            }}
            placeholder="Например: тёмное фэнтези"
            maxLength={60}
            aria-label="Новый жанр"
          />
          <button className="btn-ghost" onClick={() => addGenre(input)}>
            Добавить
          </button>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="book-genres-suggest">
          <span className="muted">Уже есть:</span>
          {suggestions.map((genre) => (
            <button
              key={genre.id}
              className="pill"
              onClick={() => addGenre(genre.name)}
            >
              {genre.name}
            </button>
          ))}
        </div>
      )}

      {hint && (
        <p className="stat-hint">
          Google Books относит книгу к: {hint}. Это рубрики магазина —
          жанрами они не считаются, но иногда подсказывают.
        </p>
      )}

      <div className="book-genres-actions">
        <button
          className="add-btn"
          onClick={() => save.mutate()}
          disabled={save.isPending}
        >
          {save.isPending ? "Сохраняю…" : "Сохранить"}
        </button>
        <button
          className="btn-ghost"
          onClick={() => {
            setDraft(genres.map((g) => g.name));   // отмена возвращает исходное
            setInput("");
            setEditing(false);
          }}
        >
          Отмена
        </button>
        {save.isError && (
          <p className="error">Не удалось сохранить: {save.error.message}</p>
        )}
      </div>
    </div>
  );
}

export default BookGenres;
