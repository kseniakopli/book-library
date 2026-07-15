// Страница книги: id из URL, свой запрос с кэшем keys.book(id).
// Выделена из App.jsx (R6).
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import BookDetail from "../components/BookDetail";

function BookPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: book,
    isLoading,
    isError,
  } = useQuery({
    queryKey: keys.book(id),
    queryFn: () => api.getBook(id),
    refetchInterval: (q) =>
      q.state.data?.enrich_status === "pending" ? 2000 : false,
  });

  function handleDeleted() {
    queryClient.invalidateQueries({ queryKey: keys.books });
    navigate("/");
  }

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError || !book)
    return (
      <div>
        <p className="muted">Книга не найдена.</p>
        <button className="btn-ghost" onClick={() => navigate("/")}>
          ← К библиотеке
        </button>
      </div>
    );

  return (
    <BookDetail
      book={book}
      onBack={() => navigate("/")}
      onDeleted={handleDeleted}
    />
  );
}

export default BookPage;
