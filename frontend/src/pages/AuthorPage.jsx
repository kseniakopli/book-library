// Страница автора (задача 97): все книги одного человека в одном месте.
//
// Две стопки, и это не украшение: «на полке» — то, что читатель завёл у себя,
// «есть в каталоге» — книги того же автора, попавшие в базу вместе с циклами,
// но на полку не положенные. Ради второй стопки страница и задумывалась —
// иначе она повторяла бы поиск по своей полке.
//
// Задача 119: макет общий со страницей цикла и книги — слева сведения
// об авторе, справа списки. Книги показываются СТРОКАМИ (`BookRow`),
// а не плитками: в колонке 4fr обложки мельчают, а строка вмещает статус.
// Плитка `BookTile` осталась у жанра — он одноколоночный.
//
// Страница ЗА ВХОДОМ (RequireAuth в App.jsx): она показывает всю полку по
// автору, включая книги вне витрины. Публичной она стала бы обходным путём
// к личной библиотеке мимо витрины, где показано только отобранное.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useAuth } from "../hooks/useAuth";
import BookRow from "../components/BookRow";
import { shelfNote } from "../lib/bookLabels";
import "../styles/entity.css";

/** Биография (задача 111): показ и правка на месте.
 *  Заполняется ВРУЧНУЮ — AI-черновик не берём: это факты о живом человеке,
 *  а выдуманная дата рождения в справочнике хуже пустого поля. */
function Bio({ authorId, bio }) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(bio ?? "");

  const save = useMutation({
    mutationFn: () => api.updateAuthor(authorId, { bio: draft }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.author(authorId) });
      // список показывает, у кого биографии нет (задача 113) — он тоже устарел
      queryClient.invalidateQueries({ queryKey: keys.authors });
      setEditing(false);
    },
  });

  if (editing) {
    return (
      <>
        <textarea
          className="entity-bio-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={6}
          maxLength={4000}
          aria-label="Биография автора"
          autoFocus
        />
        <div className="entity-bio-actions">
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
              setDraft(bio ?? "");   // отмена возвращает исходный текст
              setEditing(false);
            }}
          >
            Отмена
          </button>
          {save.isError && (
            <p className="error">Не удалось сохранить: {save.error.message}</p>
          )}
        </div>
      </>
    );
  }

  // Не-админу пустую биографию не показываем вовсе: пустой блок с подписью
  // «биографии нет» — это шум, а сделать он с ним ничего не может.
  if (!bio && !isAdmin) return null;

  return (
    <>
      {bio ? (
        <p className="entity-text">{bio}</p>
      ) : (
        <p className="muted">Биография не заполнена.</p>
      )}
      {isAdmin && (
        <button
          className="btn-ghost entity-aside-btn"
          onClick={() => setEditing(true)}
        >
          {bio ? "Изменить биографию" : "Добавить биографию"}
        </button>
      )}
    </>
  );
}

function AuthorPage() {
  const { id } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.author(id),
    queryFn: () => api.getAuthor(id),
    retry: false,
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError) return <p className="error">Автор не найден.</p>;

  const { shelf = [], catalog = [] } = data;

  return (
    <div className="entity-page">
      <div className="entity-controls">
        <Link className="btn-ghost" to="/">
          ← К библиотеке
        </Link>
      </div>

      <div className="entity-columns">
        <aside className="entity-aside">
          <h1 className="entity-title">{data.name}</h1>
          {/* оригинальное написание показываем, только если оно отличается:
              у 148 авторов из 150 его просто нет */}
          {data.name_original && data.name_ru && (
            <p className="entity-subtitle">{data.name_original}</p>
          )}
          <p className="muted entity-meta">
            {shelf.length > 0
              ? `На полке: ${shelf.length}`
              : "На полке пока ничего нет"}
            {catalog.length > 0 ? ` · в каталоге ещё ${catalog.length}` : ""}
          </p>

          <Bio authorId={data.id} bio={data.bio} />
        </aside>

        <div className="entity-lists">
          {shelf.length > 0 && (
            <section>
              <div className="entity-section-head">
                <h2 className="entity-section-title">На полке</h2>
              </div>
              <ul className="entity-rows">
                {shelf.map((book) => (
                  <BookRow
                    key={book.id}
                    book={book}
                    year={book.published_year}
                    note={shelfNote(book)}
                  />
                ))}
              </ul>
            </section>
          )}

          {catalog.length > 0 && (
            <section>
              <div className="entity-section-head">
                <h2 className="entity-section-title">Есть в каталоге</h2>
              </div>
              <p className="muted entity-section-lead">
                Книги этого автора, которых нет у вас на полке — обычно это
                тома циклов, добавленные как «что дальше».
              </p>
              <ul className="entity-rows">
                {catalog.map((book) => (
                  <BookRow
                    key={book.id}
                    book={book}
                    year={book.published_year}
                    // приглушены так же, как «что дальше» в цикле: книги
                    // не на полке, но ссылка полноценная
                    muted
                    note={
                      book.series_index ? `Книга ${book.series_index}` : null
                    }
                  />
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default AuthorPage;
