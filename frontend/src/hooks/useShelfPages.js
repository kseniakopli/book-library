// Задача 70: ленивая загрузка полки. Каждая полка — свой useInfiniteQuery
// по статусу: первая страница грузится сразу, следующие — по мере листания
// (стрелки на десктопе, докрутка свайпа на телефоне).
// Сортировка — на бэкенде (SHELF_ORDER в routers/books.py): фронт видит только
// часть книг и отсортировать полку сам уже не может.
import { useInfiniteQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

export const SHELF_PAGE = 30;

export function useShelfPages(status) {
  const query = useInfiniteQuery({
    queryKey: keys.shelf(status),
    queryFn: ({ pageParam }) =>
      api.getShelf({ status, offset: pageParam, limit: SHELF_PAGE }),
    initialPageParam: 0,
    // следующий pageParam — сколько уже загружено; всё загрузили — undefined (стоп)
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
  });

  return {
    ...query,
    books: query.data?.pages.flatMap((p) => p.items) ?? [],
    total: query.data?.pages[0]?.total ?? 0,
  };
}
