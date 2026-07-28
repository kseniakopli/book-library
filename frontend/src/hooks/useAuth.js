// Кто сейчас в сервисе (этап 9). Один запрос на всё приложение — React Query
// раздаёт результат всем компонентам из кэша.
//
// 401 — это не ошибка, а штатный ответ «не вошёл»: App по нему показывает
// страницу входа. Поэтому запрос не повторяется (retry: false) и не считается
// сломанным — иначе каждый гость видел бы «не удалось загрузить».
import { useMutation, useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

export function useAuth() {
  const query = useQuery({
    queryKey: keys.me,
    queryFn: api.getMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return {
    user: query.data ?? null,
    isAdmin: Boolean(query.data?.is_admin),
    loading: query.isLoading,
    // отличаем «не вошёл» от «сервер лежит»: у первого статус 401
    unauthorized: query.isError && query.error?.status === 401,
    failed: query.isError && query.error?.status !== 401,
  };
}

export function useLogout() {
  return useMutation({
    mutationFn: api.logout,
    // Полная перезагрузка страницы, а не queryClient.clear() (баг 26.07: кнопка
    // «Выйти» пропадала, но библиотека оставалась на экране). Перезагрузка
    // гарантированно стирает всё состояние в памяти — чужие книги не могут
    // остаться в кэше, — а куку сервер к этому моменту уже погасил.
    onSuccess: () => {
      window.location.href = "/";
    },
  });
}
