// Задача 3: ручная правка книги — промахи обогащения исправляются руками.
// Название/автор обязательны; ISBN, обложка (https), описание — опциональны,
// пустое поле очищает значение в базе.
// Задача 90в: здесь же привязка книги к циклу (выбрать существующий или создать).
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useFocusTrap } from "../hooks/useFocusTrap";

function EditBookModal({ book, onClose }) {
  const queryClient = useQueryClient();
  const modalRef = useRef(null);
  useFocusTrap(modalRef, onClose);

  const [form, setForm] = useState({
    title: book.title,
    author: book.author,
    isbn: book.isbn ?? "",
    cover_url: book.cover_url ?? "",
    description: book.description ?? "",
  });
  const set = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  // цикл: "" — без цикла, "new" — создать, иначе id существующего
  const [seriesChoice, setSeriesChoice] = useState(
    book.series_id ? String(book.series_id) : "",
  );
  const [newSeriesName, setNewSeriesName] = useState("");
  const [seriesIndex, setSeriesIndex] = useState(
    book.series_index != null ? String(book.series_index) : "",
  );

  const { data: seriesData } = useQuery({
    queryKey: keys.series,
    queryFn: api.getSeries,
  });
  const allSeries = seriesData?.series ?? [];

  const saveMutation = useMutation({
    mutationFn: async () => {
      await api.patchBook({ id: book.id, ...form });

      // привязка к циклу — отдельными запросами (цикл общий, не поле книги)
      const wasIn = book.series_id ?? null;
      let targetId = null;
      if (seriesChoice === "new" && newSeriesName.trim()) {
        const created = await api.createSeries({
          name: newSeriesName.trim(),
          author: form.author,
        });
        targetId = created.id;
      } else if (seriesChoice && seriesChoice !== "new") {
        targetId = Number(seriesChoice);
      }

      if (targetId) {
        await api.addBookToSeries({
          id: targetId,
          book_id: book.id,
          series_index: seriesIndex ? Number(seriesIndex) : null,
        });
      } else if (wasIn) {
        await api.removeBookFromSeries({ id: wasIn, bookId: book.id });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      queryClient.invalidateQueries({ queryKey: keys.series });
      onClose();
    },
  });
  const saving = saveMutation.isPending;

  const incomplete = !form.title.trim() || !form.author.trim();
  const badCover =
    form.cover_url.trim() !== "" && !form.cover_url.trim().startsWith("https://");
  const needsName = seriesChoice === "new" && !newSeriesName.trim();

  return (
    <div className="modal-overlay">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Правка книги"
        ref={modalRef}
      >
        <div className="modal-head">
          <h2 className="modal-title">Правка книги</h2>
          <button className="modal-close" onClick={onClose} aria-label="Закрыть">
            ×
          </button>
        </div>

        <label className="field">
          <span>Название</span>
          <input value={form.title} onChange={set("title")} autoFocus />
        </label>
        <label className="field">
          <span>Автор</span>
          <input value={form.author} onChange={set("author")} />
        </label>
        <label className="field">
          <span>ISBN</span>
          <input value={form.isbn} onChange={set("isbn")} />
        </label>
        <label className="field">
          <span>Обложка (ссылка https)</span>
          <input value={form.cover_url} onChange={set("cover_url")} />
        </label>
        {badCover && (
          <p className="error">Ссылка на обложку должна начинаться с https://</p>
        )}
        <label className="field">
          <span>Описание</span>
          <textarea rows={5} value={form.description} onChange={set("description")} />
        </label>

        {/* задача 90в: цикл */}
        <div className="field-row">
          <label className="field field-grow">
            <span>Цикл</span>
            <select
              value={seriesChoice}
              onChange={(e) => setSeriesChoice(e.target.value)}
            >
              <option value="">Без цикла</option>
              {allSeries.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
              <option value="new">+ Создать новый цикл…</option>
            </select>
          </label>
          {seriesChoice && (
            <label className="field field-index">
              <span>№</span>
              <input
                type="number"
                min="1"
                value={seriesIndex}
                onChange={(e) => setSeriesIndex(e.target.value)}
              />
            </label>
          )}
        </div>
        {seriesChoice === "new" && (
          <label className="field">
            <span>Название нового цикла</span>
            <input
              value={newSeriesName}
              onChange={(e) => setNewSeriesName(e.target.value)}
              placeholder="Например, «Неаполитанский квартет»"
            />
          </label>
        )}

        {saveMutation.isError && (
          <p className="error">
            Не удалось сохранить: {saveMutation.error.message}
          </p>
        )}

        <div className="modal-actions">
          <button className="btn-ghost" onClick={onClose} disabled={saving}>
            Отмена
          </button>
          <button
            className="add-btn"
            onClick={() => saveMutation.mutate()}
            disabled={saving || incomplete || badCover || needsName}
          >
            {saving ? "Сохраняю…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EditBookModal;
