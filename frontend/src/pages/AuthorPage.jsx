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
// Задача 123: админ может завести книгу автора прямо здесь. Она попадает
// в КАТАЛОГ, а не на полку — страница про библиографию, а не про то, что
// читатель у себя держит.
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
import BookSearchPicker from "../components/BookSearchPicker";
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
      // Список показывает, у кого биографии нет (задача 113) — он тоже устарел.
      // `exact: true` — ["authors"] это префикс ключа страницы автора,
      // без него строка выше дублируется, а вместе с `setQueryData`
      // такая пара молча затирает свежие данные (см. добавление книги ниже).
      queryClient.invalidateQueries({ queryKey: keys.authors, exact: true });
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
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: keys.author(id),
    queryFn: () => api.getAuthor(id),
    retry: false,
  });

  // Задача 123: книга заводится в КАТАЛОГЕ, на полку не кладётся.
  // Ответ — свежая карточка автора, поэтому кладём её в кэш сразу
  // и не делаем второй запрос (та же механика, что у цикла).
  const addBook = useMutation({
    mutationFn: (picked) =>
      api.addBookToAuthor({
        id,
        title: picked.title,
        // у книги из Google Books берём обложку и id для дозагрузки;
        // у введённой руками их просто нет
        cover_url: picked.manual ? null : (picked.cover_url ?? null),
        external_id: picked.manual ? null : (picked.external_id ?? null),
      }),
    onSuccess: (fresh) => {
      queryClient.setQueryData(keys.author(id), fresh);
      // Справочник авторов считает книги — его счётчик устарел.
      // ⚠ `exact: true` обязателен: `keys.authors` = ["authors"] — это ПРЕФИКС
      // ключа страницы ["authors", id], и без него инвалидация пометила бы
      // устаревшей карточку, которую строкой выше положили в кэш. Она бы
      // тут же перезапросилась, затерев свежий ответ. На живом бэкенде это
      // маскируется (повтор вернёт то же самое), а поймал тест.
      queryClient.invalidateQueries({ queryKey: keys.authors, exact: true });
      setAdding(false);
    },
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError) return <p className="error">Автор не найден.</p>;

  const { shelf = [], catalog = [] } = data;
  // Секция каталога у админа видна всегда: в ней живёт кнопка добавления,
  // а у автора без каталожных книг её иначе просто негде было бы нажать.
  const showCatalog = catalog.length > 0 || isAdmin;

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

          {showCatalog && (
            <section>
              <div className="entity-section-head">
                <h2 className="entity-section-title">Есть в каталоге</h2>
                {isAdmin && (
                  <button
                    className="btn-ghost"
                    onClick={() => setAdding((v) => !v)}
                  >
                    {adding ? "Отмена" : "+ Добавить книгу"}
                  </button>
                )}
              </div>
              <p className="muted entity-section-lead">
                Книги этого автора, которых нет у вас на полке — обычно это
                тома циклов, добавленные как «что дальше».
              </p>

              {adding && (
                <BookSearchPicker
                  onPick={(picked) => addBook.mutate(picked)}
                  busy={addBook.isPending}
                  // книга из базы уже привязана к своему автору: «привязать
                  // её сюда» означало бы сменить ей автора, а это делается
                  // правкой книги, где видно, что меняешь (з.123)
                  allowLocal={false}
                  localNote="уже в библиотеке"
                  // автора не спрашиваем: строку бэкенд берёт из этой сущности
                  askAuthor={false}
                  hint="Книга попадёт в каталог, а не на вашу полку — как тома циклов, добавленные «на будущее». Автор проставится этот же."
                />
              )}
              {addBook.isError && (
                <p className="error">
                  Не удалось добавить: {addBook.error.message}
                </p>
              )}

              {catalog.length === 0 && !adding && (
                <p className="muted entity-empty">
                  Других книг этого автора в библиотеке пока нет.
                </p>
              )}

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
