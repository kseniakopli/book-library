// Страница цикла (задача 89). После R4 (26.07) — композиция из трёх блоков:
// SeriesHeader (название, прогресс, статус), SeriesAside (экслибрис и описание),
// SeriesBookTree (книги цикла). Здесь остались только данные и мутации —
// то, что общее для всех трёх.
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useAuth } from "../hooks/useAuth";
import SeriesAside from "../components/SeriesAside";
import SeriesBookTree from "../components/SeriesBookTree";
import SeriesHeader from "../components/SeriesHeader";
import "../styles/series.css";

function SeriesPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // этап 9: общие данные цикла правит только админ (хвост з.90)
  const { isAdmin } = useAuth();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", author: "", description: "" });

  const { data: series, isLoading } = useQuery({
    queryKey: keys.seriesOne(id),
    queryFn: () => api.getSeriesOne(id),
  });

  // все мутации отвечают свежей карточкой цикла — кладём её в кэш сразу,
  // а полку циклов на главной помечаем устаревшей
  const refresh = (fresh) => {
    queryClient.setQueryData(keys.seriesOne(id), fresh);
    queryClient.invalidateQueries({ queryKey: keys.series });
  };

  const setStatus = useMutation({
    mutationFn: (status) => api.updateSeries({ id, status }),
    onSuccess: refresh,
  });

  const save = useMutation({
    mutationFn: () => api.updateSeries({ id, ...form }),
    onSuccess: (fresh) => {
      refresh(fresh);
      setEditing(false);
    },
  });

  // экслибрис рисуется по названию и описанию цикла — тратит токены, по кнопке
  const makeDesign = useMutation({
    mutationFn: () => api.generateSeriesDesign(id),
    onSuccess: refresh,
  });

  // picked приходит из SeriesBookSearch: либо {book_id}, либо {title, author,
  // cover_url, external_id} — второй случай заводит книгу в каталоге
  const addBook = useMutation({
    mutationFn: (picked) => api.addBookToSeries({ id, ...picked }),
    onSuccess: (fresh) => {
      refresh(fresh);
      setAdding(false);
    },
  });

  const removeBook = useMutation({
    mutationFn: (bookId) => api.removeBookFromSeries({ id, bookId }),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: () => api.deleteSeries(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.series });
      navigate("/");
    },
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (!series) return <p className="error">Цикл не найден</p>;

  return (
    <div className="series-page">
      <div className="series-controls">
        <Link className="btn-ghost" to="/">
          ← К библиотеке
        </Link>
        {isAdmin && (
          <button
            className="btn-danger"
            onClick={() => {
              if (window.confirm("Удалить цикл? Книги останутся в библиотеке.")) {
                remove.mutate();
              }
            }}
          >
            Удалить цикл
          </button>
        )}
      </div>

      <SeriesHeader
        series={series}
        editing={editing}
        form={form}
        onFormChange={setForm}
        onStatus={(status) => setStatus.mutate(status)}
        statusPending={setStatus.isPending}
      />

      <div className="series-layout">
        <SeriesAside
          series={series}
          isAdmin={isAdmin}
          editing={editing}
          form={form}
          onFormChange={setForm}
          onStartEdit={() => {
            setForm({
              name: series.name,
              author: series.author ?? "",
              description: series.description ?? "",
            });
            setEditing(true);
          }}
          onCancelEdit={() => setEditing(false)}
          onSave={() => save.mutate()}
          savePending={save.isPending}
          onGenerateDesign={() => makeDesign.mutate()}
          designPending={makeDesign.isPending}
          designError={makeDesign.isError ? makeDesign.error : null}
        />

        <SeriesBookTree
          books={series.books}
          adding={adding}
          onToggleAdding={() => setAdding((v) => !v)}
          onPick={(picked) => addBook.mutate(picked)}
          addPending={addBook.isPending}
          onRemove={(bookId) => removeBook.mutate(bookId)}
        />
      </div>
    </div>
  );
}

export default SeriesPage;
