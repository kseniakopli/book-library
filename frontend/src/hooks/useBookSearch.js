// Поиск книги через /search — единственная реализация на всё приложение (R1, 26.07).
//
// До этого один и тот же код жил в трёх местах (SearchModal, SeriesBookSearch,
// HomePage): свой useState для debounce, свой useEffect с таймером, свой useQuery
// и свой разбор результатов. Правка вроде «искать от 3 символов» требовала трёх
// одинаковых изменений — и однажды они бы разошлись.
//
// Хук отвечает за «как искать», компоненты — за «что делать с найденным»:
// модалка добавляет на полку, поиск цикла привязывает к серии, главная показывает
// карточки. Поэтому наружу отдаются и сырые results, и разложенные группы.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

export const MIN_CHARS = 3;      // короче — не дёргаем бэкенд и Google API
export const DEBOUNCE_MS = 300;  // не ищем на каждую букву

export function useBookSearch(term) {
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebounced((term || "").trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [term]);

  const enabled = debounced.length >= MIN_CHARS;
  const query = useQuery({
    queryKey: keys.search(debounced),
    queryFn: () => api.searchBooks(debounced),
    enabled,
  });

  // пока запрос выключен, старые данные из кэша показывать нельзя —
  // иначе после стирания строки на экране остаётся прошлая выдача
  const results = enabled ? (query.data?.results ?? []) : [];

  return {
    term: debounced,
    enabled,                       // введено ли достаточно символов
    results,
    searching: query.isFetching,
    isError: query.isError,
    // ничего не нашлось — компоненты по этому признаку предлагают ручной ввод
    nothingFound: enabled && !query.isFetching && results.length === 0,
    // группы (задача 90): что уже на полке, что есть в базе, что нашлось у Google.
    // catalog — это кэш прошлых запросов к Google, а не наши книги, поэтому он
    // относится к google-группе.
    onShelf: results.filter((r) => r.on_shelf),
    inCatalog: results.filter((r) => !r.on_shelf && r.source === "library"),
    fromGoogle: results.filter((r) => !r.on_shelf && r.source !== "library"),
  };
}
