// Публичная витрина (задача 30): отобранные книги владельца — страница,
// на которую ведут QR печатных карточек.
//
// Открывается БЕЗ входа, поэтому здесь нет ни useAuth, ни запросов к закрытому
// API: только /public/{slug}. Гость видит книги и их оформление; оценки, статусы
// и даты чтения сюда не приходят вовсе (см. routers/public.py).
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useTheme } from "../hooks/useTheme";
import ShowcaseShelf from "../components/ShowcaseShelf";
import ShowcaseFeatures from "../components/ShowcaseFeatures";
import ShowcaseWaitlist from "../components/ShowcaseWaitlist";
import "../styles/showcase.css";

function ShowcasePage() {
  const { slug } = useParams();
  const { theme } = useTheme();
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.showcase(slug),
    queryFn: () => api.getShowcase(slug),
    retry: false,
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError) return <p className="error">Такой витрины нет.</p>;

  return (
    <main className="showcase">
      <header className="showcase-head">
        <h1 className="showcase-heading">{data.title}</h1>
        {data.intro && <p className="showcase-intro">{data.intro}</p>}
      </header>

      {data.books.length === 0 ? (
        <p className="muted">Пока здесь пусто.</p>
      ) : (
        <ShowcaseShelf books={data.books} slug={slug} theme={theme} />
      )}

      {/* Витрина — не только полка, но и вход в сервис: человек приходит сюда
          по QR с бумажной карточки, ничего о nocturne не зная. Дальше — чем
          это может быть полезно ему самому и как остаться на связи. */}
      <ShowcaseFeatures />
      <ShowcaseWaitlist />

      <footer className="showcase-foot">
        <p className="muted">
          nocturne — вечер вокруг книги: музыка, угощения и ароматы под её
          настроение.
        </p>
      </footer>
    </main>
  );
}

export default ShowcasePage;
