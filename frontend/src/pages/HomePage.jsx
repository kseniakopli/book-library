// Главная: шапка, поиск по библиотеке, полки. Логика вынесена в хуки
// (useShelves / useCsvImport / useStickyHeader / useShelfPositions),
// шапка — в LibraryHeader (ревью 19.07). Здесь остались состав и состояния экрана.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useTheme } from "../hooks/useTheme";
import { useDisplayMode } from "../hooks/useDisplayMode";
import { useStickyHeader } from "../hooks/useStickyHeader";
import { useShelves } from "../hooks/useShelves";
import { useCsvImport } from "../hooks/useCsvImport";
import { useShelfPositions } from "../hooks/useShelfPositions";
import BookCard from "../components/BookCard";
import LibraryHeader from "../components/LibraryHeader";
import Onboarding from "../components/Onboarding";
import RecommendationShelf from "../components/RecommendationShelf";
import SearchModal from "../components/SearchModal";
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

  // Список книг: кэш keys.books (без собственного поллинга — задача 56б)
  const queryClient = useQueryClient();
  const {
    data: books = [],
    isLoading: loading,
    isError: booksError,
    refetch: refetchBooks,
  } = useQuery({
    queryKey: keys.books,
    queryFn: api.getBooks,
  });

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

  const shelves = useShelves(books);

  // общие пропсы полок — чтобы не повторять их у каждой
  const shelfCards = { symbolMode, designs, theme };

  const openBook = (b) => navigate(`/books/${b.id}`);

  function closeModal() {
    setShowModal(false);
    addButtonRef.current?.focus();   // вернуть фокус туда, откуда открывали
  }

  const trimmed = filter.trim().toLowerCase();
  const filtered = trimmed
    ? books.filter(
        (b) =>
          b.title.toLowerCase().includes(trimmed) ||
          b.author.toLowerCase().includes(trimmed),
      )
    : null;

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
      ) : books.length === 0 ? (
        // задача 21: библиотека пуста — онбординг вместо пустых полок
        <Onboarding onAddBook={() => setShowModal(true)} />
      ) : filtered ? (
        filtered.length === 0 ? (
          <p className="muted">Ничего не найдено в библиотеке.</p>
        ) : (
          <div className="grid">
            {filtered.map((book) => (
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
        )
      ) : (
        <>
          {/* «Читаю» — только если такие книги есть */}
          {shelves.reading.length > 0 && (
            <Shelf
              title="Читаю"
              books={shelves.reading}
              onSelect={openBook}
              {...shelfCards}
              {...shelfProps("Читаю")}
            />
          )}
          <Shelf
            title="Прочитано"
            books={shelves.read}
            onSelect={openBook}
            {...shelfCards}
            {...shelfProps("Прочитано")}
          />
          <Shelf
            title="Хочу прочитать"
            books={shelves.want}
            onSelect={openBook}
            {...shelfCards}
            {...shelfProps("Хочу прочитать")}
          />
          <RecommendationShelf />
        </>
      )}

      {showModal && <SearchModal onClose={closeModal} />}
    </>
  );
}

export default HomePage;
