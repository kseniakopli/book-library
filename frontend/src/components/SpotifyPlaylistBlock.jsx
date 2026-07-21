// Плейлист книги в Spotify (этап 10.2). Вынесено из BookDetail (ревью 19.07):
// блок самодостаточный — сам владеет мутацией и своими сообщениями.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

function SpotifyPlaylistBlock({ book, hasMusic }) {
  const queryClient = useQueryClient();

  // первый раз откроется окно авторизации Spotify,
  // после него плейлисты создаются в один клик
  const playlist = useMutation({
    mutationFn: () => api.createPlaylist(book.id),
    onSuccess: (data) => {
      if (data.status === "auth_required") {
        window.open(data.auth_url, "_blank", "noopener");
        return;
      }
      queryClient.invalidateQueries({ queryKey: keys.books });
    },
  });

  // Пока музыки нет, блок не показываем вовсе: кнопка «Создать плейлист»
  // всё равно ничего не может — плейлист собирается из музыкальной подборки.
  // Обычно он появляется сам вместе с атмосферой; кнопка остаётся запасным
  // путём (например, если при генерации не было авторизации в Spotify).
  if (!book.spotify_playlist_url && !hasMusic) return null;

  return (
    <>
      <div className="playlist-row">
        {book.spotify_playlist_url ? (
          <a
            className="btn-ghost playlist-link"
            href={book.spotify_playlist_url}
            target="_blank"
            rel="noreferrer"
          >
            ♫ Открыть плейлист в Spotify
          </a>
        ) : (
          <button
            className="btn-ghost"
            onClick={() => playlist.mutate()}
            disabled={playlist.isPending}
            title="Обычно плейлист собирается сам вместе с атмосферой — эта кнопка нужна, если тогда не было авторизации в Spotify"
          >
            {playlist.isPending
              ? "Создаю плейлист…"
              : "♫ Создать плейлист в Spotify"}
          </button>
        )}
      </div>

      {playlist.data?.status === "auth_required" && (
        <p className="muted">
          Разрешите доступ в открывшемся окне Spotify — плейлист создастся
          автоматически.
        </p>
      )}
      {playlist.data?.not_found?.length > 0 && (
        <p className="muted">
          Не нашлись в Spotify: {playlist.data.not_found.join(", ")}
        </p>
      )}
      {playlist.isError && (
        <p className="error">Плейлист не создался: {playlist.error.message}</p>
      )}
    </>
  );
}

export default SpotifyPlaylistBlock;
