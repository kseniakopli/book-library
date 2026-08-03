// Справочник авторов (задача 111, первая часть).
//
// ⚠ Раздел про то, что есть в БАЗЕ сервиса, а не про личную полку (решение
// Ксении 03.08): числа считаются по общему каталогу, и список одинаков для
// всех. Что из этого лежит на полке лично у читателя, показывает страница
// автора — там книги разложены на две стопки.
//
// Разметка общая с жанрами (`components/CatalogList`, ревью 03.08).
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import CatalogList from "../components/CatalogList";

function AuthorsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.authors,
    queryFn: api.getAuthors,
  });

  return (
    <CatalogList
      title="Авторы"
      items={data?.authors ?? []}
      hrefBase="/authors"
      isLoading={isLoading}
      isError={isError}
      errorText="Не удалось загрузить список авторов."
      emptyText="Авторы появятся, когда в библиотеке будут книги."
    />
  );
}

export default AuthorsPage;
