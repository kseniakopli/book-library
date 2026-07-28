// Главная: шапка, поиск по библиотеке, полки. Логика вынесена в хуки
// (useShelfPages / useCsvImport / useStickyHeader / useShelfPositions),
// шапка — в LibraryHeader (ревью 19.07). Здесь остались состав и состояния экрана.
// Задача 70: полки грузятся постранично, поиск — целиком серверный.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useTheme } from "../hooks/useTheme";
import { useDisplayMode } from "../hooks/useDisplayMode";
import { useStickyHeader } from "../hooks/useStickyHeader";
import { useShelfPages } from "../hooks/useShelfPages";
import { useBookSearch } from "../hooks/useBookSearch";
import { useCsvImport } from "../hooks/useCsvImport";
import { useShelfPositions } from "../hooks/useShelfPositions";
import BookCard from "../components/BookCard";
import LibraryHeader from "../components/LibraryHeader";
import Onboarding from "../components/Onboarding";
import RecommendationShelf from "../components/RecommendationShelf";
import SearchModal from "../components/SearchModal";
import SeriesShelf from "../components/SeriesShelf";
import Shelf from "../components/Shelf";

function HomePage() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { mode, toggleMode } = useDisplayMode();
  const symbolMode = mode === "symbols";

  const compactHeader = useStickyHeader();
  const csv = useCsvImport();
  const shelfProps = useShelfPositions();

  const [filter, setFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const addButtonRef = useRef(null);

  // Задача 70: каждая полка грузится постранично своим запросом (по статусу);
  // сортировка и общее число — на бэкенде. Инвалидация по префиксу keys.books
  // задевает и эти ключи (["books", "shelf", ...]).
  const queryClient = useQueryClient();
  const reading = useShelfPages("reading");
  const read = useShelfPages("read");
  const want = useShelfPages("want");
  const shelvesList = [reading, read, want];
  // не дёргаем следующую страницу, пока грузится текущая (сенсор свайпа
  // может сработать несколько раз подряд)
  const loadMore = (shelf) => () =>
    !shelf.isFetchingNextPage && shelf.fetchNextPage();

  const books = shelvesList.flatMap((s) => s.books);   // загруженная часть библиотеки
  const totalBooks = shelvesList.reduce((n, s) => n + s.total, 0);
  const loading = shelvesList.some((s) => s.isLoading);
  const booksError = shelvesList.some((s) => s.isError);
  const refetchBooks = () => shelvesList.forEach((s) => s.refetch());

  // Задача 56б: пока в списке есть pending-книги, поллим ЛЁГКИЙ счётчик
  // (одно число), а не весь список. Счётчик уменьшился — значит, какие-то
  // книги дообогатились: тогда (и только тогда) перечитываем список.
  const anyPending = books.some((b) => b.enrich_status === "pending");
  const { data: pendingData } = useQuery({
    queryKey: keys.pendingCount,
    queryFn: api.getPendingCount,
    enabled: anyPending,
    refetchInterval: 2000,
  });
  const pendingCount = pendingData?.pending;
  const prevPending = useRef(null);
  useEffect(() => {
    if (pendingCount == null) return;
    if (prevPending.current != null && pendingCount < prevPending.current) {
      queryClient.invalidateQueries({ queryKey: keys.books });
    }
    prevPending.current = pendingCount;
  }, [pendingCount, queryClient]);

  // Символьный режим (задача 66): символы+палитры тянем один раз и только когда
  // режим включён; строим карту book_id → паспорт для карточек
  const { data: designData } = useQuery({
    queryKey: keys.designSummary,
    queryFn: api.getDesignSummary,
    enabled: symbolMode,
  });
  const designs = useMemo(() => {
    const map = {};
    for (const d of designData?.designs ?? []) map[d.book_id] = d;
    return map;
  }, [designData]);

  // общие пропсы полок — чтобы не повторять их у каждой
  const shelfCards = { symbolMode, designs, theme };

  const openBook = (b) => navigate(`/books/${b.id}`);

  function closeModal() {
    setShowModal(false);
    addButtonRef.current?.focus();   // вернуть фокус туда, откуда открывали
  }

  // Задача 70: поиск целиком СЕРВЕРНЫЙ (/search ищет по каталогу и помечает
  // полочные книги). Клиентский фильтр убран: фронт видит не всю библиотеку,
  // и фильтр по загруженному молча терял бы книги с неподгруженных страниц.
  // R1: debounce, запрос и разбор на группы — в общем хуке useBookSearch.
  const trimmed = filter.trim();
  const search = useBookSearch(filter);
  const searching = search.enabled;
  // совпадения на полке рисуем карточками книг — приводим к форме BookCard
  const shelfHits = search.onShelf.map((r) => ({
    id: r.book_id,
    title: r.title,
    author: r.author,
    cover_url: r.cover_url,
    status: r.status,
    rating: r.rating,
  }));
  const inBaseHits = search.inCatalog;
  const googleHits = search.fromGoogle;

  const addToShelf = useMutation({
    mutationFn: (item) =>
      api.createBook({
        title: item.title,
        author: item.author,
        cover_url: item.cover_url,
        external_id: item.external_id,
        book_id: item.book_id, // из каталога — переиспускаем запись, без дубля
        status: "want",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      queryClient.invalidateQueries({ queryKey: keys.series });
      // Книга легла на полку — выходим из поиска к полкам (баг 24.07: результаты
      // оставались висеть, и было непонятно, добавилась книга или нет).
      // Полка «Хочу прочитать» уже перечитана инвалидацией — новая книга видна.
      setFilter("");
    },
  });

  return (
    <>
      <LibraryHeader
        compact={compactHeader}
        symbolMode={symbolMode}
        onToggleMode={toggleMode}
        theme={theme}
        onToggleTheme={toggleTheme}
        csv={csv}
        onAddBook={() => setShowModal(true)}
        addButtonRef={addButtonRef}
      />

      <input
        className="lib-search"
        placeholder="Поиск по библиотеке…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />

      {csv.message && <p className="muted">{csv.message}</p>}
      {csv.error && <p className="error">Импорт не удался: {csv.error.message}</p>}

      {loading ? (
        <p className="muted">Загрузка…</p>
      ) : booksError ? (
        <p className="error">
          Не удалось загрузить библиотеку.{" "}
          <button className="btn-ghost" onClick={() => refetchBooks()}>
            Повторить
          </button>
        </p>
      ) : totalBooks === 0 ? (
        // задача 21: библиотека пуста — онбординг вместо пустых полок
        <Onboarding onAddBook={() => setShowModal(true)} />
      ) : trimmed && !searching ? (
        // поиск серверный и начинается с 3 символов (как в модалке добавления)
        <p className="muted">Введите минимум 3 символа для поиска.</p>
      ) : searching ? (
        <>
          {/* совпадения на полке */}
          {shelfHits.length > 0 && (
            <div className="grid">
              {shelfHits.map((book) => (
                <BookCard
                  key={book.id}
                  book={book}
                  onSelect={openBook}
                  symbolMode={symbolMode}
                  design={designs[book.id]}
                  theme={theme}
                />
              ))}
            </div>
          )}

          {/* задача 90: книги, которых нет на полке — раздельно по источнику */}
          {[
            { title: "Есть в базе, но не на вашей полке", items: inBaseHits },
            { title: "Найдено в Google Books", items: googleHits },
          ].map(
            ({ title, items }) =>
              items.length > 0 && (
                <div className="catalog-hits" key={title}>
                  <h3 className="catalog-hits-title">{title}</h3>
                  <ul className="catalog-hit-list">
                    {items.map((item, i) => (
                      <li className="catalog-hit" key={`${item.title}-${i}`}>
                        <span className="catalog-hit-text">
                          <span className="catalog-hit-title">{item.title}</span>
                          <span className="catalog-hit-author">{item.author}</span>
                        </span>
                        <button
                          className="btn-ghost"
                          onClick={() => addToShelf.mutate(item)}
                          disabled={addToShelf.isPending}
                        >
                          + На полку
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ),
          )}

          {search.searching && search.results.length === 0 && (
            <p className="muted">Ищу в каталоге…</p>
          )}
          {search.nothingFound && <p className="muted">Ничего не найдено.</p>}
          {addToShelf.isError && (
            <p className="error">
              Не удалось добавить: {addToShelf.error.message}
            </p>
          )}
        </>
      ) : (
        <>
          {/* «Читаю» — только если такие книги есть */}
          {reading.total > 0 && (
            <Shelf
              title="Читаю"
              books={reading.books}
              total={reading.total}
              hasMore={reading.hasNextPage}
              onLoadMore={loadMore(reading)}
              onSelect={openBook}
              {...shelfCards}
              {...shelfProps("Читаю")}
            />
          )}
          <Shelf
            title="Прочитано"
            books={read.books}
            total={read.total}
            hasMore={read.hasNextPage}
            onLoadMore={loadMore(read)}
            onSelect={openBook}
            {...shelfCards}
            {...shelfProps("Прочитано")}
          />
          <Shelf
            title="Хочу прочитать"
            books={want.books}
            total={want.total}
            hasMore={want.hasNextPage}
            onLoadMore={loadMore(want)}
            onSelect={openBook}
            {...shelfCards}
            {...shelfProps("Хочу прочитать")}
          />
          {/* задача 89: полка циклов — между книгами и рекомендациями */}
          <SeriesShelf />
          <RecommendationShelf />
        </>
      )}

      {showModal && <SearchModal onClose={closeModal} />}
    </>
  );
}

export default HomePage;
