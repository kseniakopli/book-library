// Онбординг (задача 21): показывается вместо полок, пока библиотека пуста.
// Три шага + кнопка «наполнить примерами» — примеры добавляются как обычные
// книги (обложки подтянет фоновое обогащение — заодно демо этого механизма).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

const SAMPLE_BOOKS = [
  { title: "Мастер и Маргарита", author: "Михаил Булгаков", status: "read" },
  {
    title: "Понедельник начинается в субботу",
    author: "Аркадий и Борис Стругацкие",
    status: "reading",
  },
  {
    title: "Сто лет одиночества",
    author: "Габриэль Гарсиа Маркес",
    status: "want",
  },
];

function Onboarding({ onAddBook }) {
  const queryClient = useQueryClient();

  const fillMutation = useMutation({
    mutationFn: async () => {
      // последовательно: у SQLite один писатель, не толкаемся
      for (const book of SAMPLE_BOOKS) {
        await api.createBook(book);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.books }),
  });

  return (
    <section className="onboarding">
      <h2 className="onboarding-title">Добро пожаловать в nocturne</h2>
      <p className="muted">Три шага до первого атмосферного вечера:</p>

      <ol className="onboarding-steps">
        <li>
          <b>Добавьте книги.</b> Найдите их в каталоге кнопкой
          «+ Добавить книгу» или импортируйте CSV со своей библиотекой —
          обложки и описания подтянутся сами.
        </li>
        <li>
          <b>Соберите атмосферу.</b> На странице книги одна кнопка попросит
          Claude и ChatGPT подобрать музыку, угощения и ароматы —
          два варианта на выбор.
        </li>
        <li>
          <b>Оформите вечер.</b> Паспорт оформления перекрасит карточку под
          настроение книги и нарисует её символ, плейлист уедет в Spotify,
          а печатная карточка — в саму книгу.
        </li>
      </ol>

      <div className="onboarding-actions">
        <button className="add-btn" onClick={onAddBook}>
          + Добавить первую книгу
        </button>
        <button
          className="btn-ghost"
          onClick={() => fillMutation.mutate()}
          disabled={fillMutation.isPending}
        >
          {fillMutation.isPending
            ? "Наполняю…"
            : "Наполнить примерами (3 книги)"}
        </button>
      </div>

      {fillMutation.isError && (
        <p className="error">
          Не получилось добавить примеры: {fillMutation.error.message}
        </p>
      )}
      <p className="muted onboarding-note">
        Примеры — обычные книги: их можно удалить, а атмосферу для них
        генерируете вы сами (это платные AI-вызовы).
      </p>
    </section>
  );
}

export default Onboarding;
