// Разбор ссылок Spotify (задача 29б).
//
// Живёт в lib/, а не рядом с компонентом: функция чистая и тестируется без
// рендера, а экспорт не-компонента из файла компонента ломает Fast Refresh
// (на это ругается oxlint).

/**
 * id плейлиста из сохранённой ссылки:
 *   https://open.spotify.com/playlist/<id>?si=…  →  <id>
 *
 * В `Book.spotify_playlist_url` лежит то, что вернул Spotify, но однажды туда
 * может попасть мусор после ручной правки в базе. Тогда возвращаем null —
 * плеер просто не показывается, страница книги продолжает работать.
 */
export function playlistEmbedId(url) {
  if (typeof url !== "string") return null;
  const match = url.match(/playlist\/([A-Za-z0-9]+)/);
  return match ? match[1] : null;
}
