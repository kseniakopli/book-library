// Задача 3: ручная правка книги — промахи обогащения исправляются руками.
// Название/автор обязательны; ISBN, обложка (https), описание — опциональны,
// пустое поле очищает значение в базе.
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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

  const saveMutation = useMutation({
    mutationFn: () => api.patchBook({ id: book.id, ...form }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      onClose();
    },
  });
  const saving = saveMutation.isPending;

  const incomplete = !form.title.trim() || !form.author.trim();
  const badCover =
    form.cover_url.trim() !== "" && !form.cover_url.trim().startsWith("https://");

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
            disabled={saving || incomplete || badCover}
          >
            {saving ? "Сохраняю…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EditBookModal;
