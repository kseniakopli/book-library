// Поиск книги для добавления в цикл (задача 89).
//
// Отличие от SearchModal: выбранная книга НЕ попадает на полку, а привязывается
// к циклу; если её нет в каталоге — заводится там (без UserBook).
//
// ⚠ Задача 123: сам поиск переехал в общий `BookSearchPicker` — такой же
// экран понадобился на странице автора. Здесь осталось то, что есть только
// у цикла: номер тома и раскладка выбранного в тело запроса.
import { useState } from "react";
import BookSearchPicker from "./BookSearchPicker";

function SeriesBookSearch({ onPick, busy }) {
  const [index, setIndex] = useState("");

  const numberField = (
    <input
      className="series-index-input"
      type="number"
      min="1"
      placeholder="№"
      value={index}
      onChange={(e) => setIndex(e.target.value)}
      aria-label="Номер книги в цикле"
    />
  );

  // книга из базы приезжает как book_id, новая — набором полей;
  // бэкенд по этому и различает «привязать» и «завести в каталоге»
  const pick = (item) =>
    onPick({
      book_id: item.book_id ?? undefined,
      title: item.book_id ? undefined : item.title,
      author: item.book_id ? undefined : item.author,
      cover_url: item.book_id ? undefined : item.cover_url,
      external_id: item.book_id ? undefined : item.external_id,
      series_index: index ? Number(index) : null,
    });

  return (
    <BookSearchPicker
      onPick={pick}
      busy={busy}
      extraField={numberField}
      hint="Книги, которых у вас ещё нет, тоже можно добавить — они покажут, что читать дальше. На полку они не попадут."
    />
  );
}

export default SeriesBookSearch;
