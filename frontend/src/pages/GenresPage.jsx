// Справочник жанров (задача 112).
//
// ⚠ Как и авторы, считается по ОБЩЕМУ каталогу, а не по полке спрашивающего.
//
// Жанры заводятся ВРУЧНУЮ на странице книги: Google Books отдаёт
// «Fiction / General» — это рубрикатор магазина, а не жанр, и источником
// данных он здесь не работает.
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import CatalogList from "../components/CatalogList";

function GenresPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.genres,
    queryFn: api.getGenres,
  });

  return (
    <CatalogList
      title="Жанры"
      items={data?.genres ?? []}
      hrefBase="/genres"
      isLoading={isLoading}
      isError={isError}
      errorText="Не удалось загрузить список жанров."
      emptyText={
        "Жанров пока нет. Они проставляются вручную на странице книги — " +
        "Google Books присылает рубрики вроде «Fiction / General», " +
        "и жанрами они не считаются."
      }
    />
  );
}

export default GenresPage;
