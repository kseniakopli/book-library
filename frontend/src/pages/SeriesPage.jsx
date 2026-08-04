// Страница цикла (задача 89). После R4 (26.07) — композиция из блоков:
// SeriesAside (экслибрис, название, прогресс, статус, описание) и
// SeriesBookTree (книги цикла). Здесь остались только данные и мутации —
// то, что общее для обоих.
//
// ⚠ Задача 119: макет общий со страницами книги и автора (`entity.css`) —
// слева сведения о цикле, справа список томов. Бывший `SeriesHeader` был
// шапкой НАД колонками и влился в левую колонку, файл удалён.
// `series.css` остался ради того, что есть только у цикла: крупный
// экслибрис, полка циклов на главной и поиск книги для добавления.
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useAuth } from "../hooks/useAuth";
import SeriesAside from "../components/SeriesAside";
import SeriesBookTree from "../components/SeriesBookTree";
import "../styles/entity.css";
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
    <div className="entity-page">
      <div className="entity-controls">
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

      <div className="entity-columns">
        <aside className="entity-aside">
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
            onStatus={(status) => setStatus.mutate(status)}
            statusPending={setStatus.isPending}
            onGenerateDesign={() => makeDesign.mutate()}
            designPending={makeDesign.isPending}
            designError={makeDesign.isError ? makeDesign.error : null}
          />
        </aside>

        <div className="entity-lists">
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
    </div>
  );
}

export default SeriesPage;
