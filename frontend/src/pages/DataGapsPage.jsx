// Админский раздел «Заполнение данных» (задача 113).
//
// ⚠ Сначала цифры, потом списки — так задача и была поставлена. Доли важнее
// перечня: двадцать книг без описания заполняются за вечер, сто восемьдесят —
// нет, и во втором случае разговор не про интерфейс, а про источник данных.
//
// Заполняется всё ВРУЧНУЮ: описания правятся в карточке книги, жанры там же
// (з.112), биографии — на странице автора (з.111).
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import "../styles/stats.css";
// список объектов рисуется теми же правилами, что справочники авторов
// и жанров (ревью 03.08: раньше это был `authors.css` — чужие классы
// на служебной странице)
import "../styles/catalog.css";

const CARDS = [
  {
    kind: "no_description",
    label: "Книги без описания",
    // з.106: без аннотации модель подбирает музыку и оформление по названию
    // и автору — это объясняет часть однообразия лучше любых запретов
    hint: "модель угадывает содержание по названию",
  },
  { kind: "no_genres", label: "Книги без жанров", hint: "не попадают в справочник" },
  { kind: "no_cover", label: "Книги без обложки", hint: "серая заглушка на полке" },
  {
    kind: "no_design",
    label: "Книги без паспорта",
    hint: "нет палитры и символа — заметно на витрине",
  },
  { kind: "no_bio", label: "Авторы без биографии", hint: "пустая страница автора" },
];

/** Доля считается здесь, а не на бэкенде: там только факты, иначе округление
 *  в интерфейсе и в отчёте разъедется при первой же правке. */
function share(part, total) {
  if (!total) return null;
  return Math.round((part / total) * 100);
}

function GapCard({ card, count, total, active, onSelect }) {
  const percent = share(count, total);
  return (
    <button
      className={"stat-card gap-card" + (active ? " gap-card-active" : "")}
      onClick={() => onSelect(card.kind)}
      aria-pressed={active}
    >
      {/* число и доля — в одной строке: раньше процент стоял внутри пояснения,
          и строка вроде «35% · модель угадывает содержание по названию»
          переносилась на три строки, растягивая карточку неровно */}
      <div className="gap-value-row">
        <span className="stat-value">{count}</span>
        {percent !== null && <span className="gap-percent">{percent}%</span>}
      </div>
      <div className="stat-label">{card.label}</div>
      {/* пояснение прижато к низу — подписи в карточках разной длины,
          и без этого они «плавают» на разной высоте */}
      <div className="stat-hint gap-hint">{card.hint}</div>
    </button>
  );
}

function DataGapsPage() {
  const [kind, setKind] = useState(null);
  const queryClient = useQueryClient();

  const summary = useQuery({
    queryKey: keys.dataGaps,
    queryFn: api.getDataGaps,
    retry: false,
  });

  // Задача 116: паспорта книгам, пришедшим импортом (там фоновая генерация
  // не вызывается вовсе). Партией — каждый паспорт это вызов Claude.
  const backfill = useMutation({
    mutationFn: api.backfillDesign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.dataGaps });
    },
  });

  const list = useQuery({
    queryKey: keys.dataGapItems(kind),
    queryFn: () => api.getDataGapItems(kind),
    enabled: Boolean(kind),
  });

  const data = summary.data;
  const counts = data && {
    ...data.books,
    no_bio: data.authors.no_bio,
  };
  const totals = data && {
    no_description: data.books_total,
    no_genres: data.books_total,
    no_cover: data.books_total,
    no_design: data.books_total,
    no_bio: data.authors_total,
  };

  return (
    <div className="stats-page">
      <header className="stats-header">
        <Link to="/" className="btn-ghost">
          ← В библиотеку
        </Link>
        <h1 className="title">Заполнение данных</h1>
      </header>

      {summary.isPending && <p className="muted">Считаю…</p>}
      {summary.isError && (
        <p className="error">
          Не удалось загрузить сводку. Раздел доступен только администратору.
        </p>
      )}

      {data && (
        <>
          <p className="muted">
            Каталог: {data.books_total} книг, {data.authors_total} авторов.
            Заполняется вручную — нажмите карточку, чтобы увидеть список.
          </p>

          <div className="stat-cards">
            {CARDS.map((card) => (
              <GapCard
                key={card.kind}
                card={card}
                count={counts[card.kind]}
                total={totals[card.kind]}
                active={kind === card.kind}
                onSelect={setKind}
              />
            ))}
          </div>

          {kind && (
            <section className="stat-block">
              <h2 className="stat-title">
                {CARDS.find((c) => c.kind === kind).label}
                <span className="stat-note">первые 50</span>
              </h2>

              {/* Задача 116: единственный вид неполноты, который чинится
                  не руками. Остальное — описания, жанры, биографии —
                  заполняет человек, и кнопки там быть не может. */}
              {kind === "no_design" && (
                <div className="gap-action">
                  <button
                    className="btn-ghost"
                    onClick={() => backfill.mutate()}
                    disabled={backfill.isPending}
                  >
                    {backfill.isPending
                      ? "Запускаю…"
                      : "Догенерировать 10 паспортов"}
                  </button>
                  <p className="stat-hint">
                    Каждый паспорт — вызов Claude, поэтому партиями. Готовятся
                    в фоне: обновите страницу через минуту.
                  </p>
                  {backfill.data && (
                    <p className="muted">
                      Запущено: {backfill.data.scheduled}, осталось без
                      паспорта: {backfill.data.remaining}.
                    </p>
                  )}
                  {backfill.isError && (
                    <p className="error">
                      Не удалось запустить: {backfill.error.message}
                    </p>
                  )}
                </div>
              )}

              {list.isPending && <p className="muted">Загрузка…</p>}
              {list.data?.items.length === 0 && (
                <p className="muted">Здесь всё заполнено.</p>
              )}
              {list.data?.items.length > 0 && (
                <ul className="catalog-list">
                  {list.data.items.map((item) => (
                    <li key={`${item.kind}-${item.id}`}>
                      <Link
                        className="catalog-item"
                        to={
                          item.kind === "author"
                            ? `/authors/${item.id}`
                            : `/books/${item.id}`
                        }
                      >
                        <span className="catalog-item-name">{item.name}</span>
                        {item.author && (
                          <span className="catalog-item-count">{item.author}</span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default DataGapsPage;
