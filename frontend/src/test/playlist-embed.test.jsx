// Embed-плеер плейлиста (задача 29б).
//
// Разбор ссылки вынесен в функцию не ради красоты: в `spotify_playlist_url`
// лежит то, что вернул Spotify, и туда же однажды может попасть мусор после
// ручной правки в базе. Плеер тогда просто не показывается — страница книги
// от этого падать не должна.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SpotifyPlaylistBlock from "../components/SpotifyPlaylistBlock";
import { playlistEmbedId } from "../lib/spotify";
import { renderApp } from "./utils";
import { server } from "./server";

const URL = "https://open.spotify.com/playlist/4PHjdTvj7io13Kd5G7d6Ys";

test("id вытаскивается из ссылки, в том числе с хвостом ?si=", () => {
  expect(playlistEmbedId(URL)).toBe("4PHjdTvj7io13Kd5G7d6Ys");
  expect(playlistEmbedId(`${URL}?si=abc123`)).toBe("4PHjdTvj7io13Kd5G7d6Ys");
});

test("мусорная или пустая ссылка — просто нет id", () => {
  expect(playlistEmbedId("https://example.com/nothing")).toBe(null);
  expect(playlistEmbedId(null)).toBe(null);
  expect(playlistEmbedId(undefined)).toBe(null);
});

const renderBlock = (book) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SpotifyPlaylistBlock book={book} hasMusic />
    </QueryClientProvider>,
  );

test("есть плейлист — рядом со списком остаётся ссылка «открыть»", () => {
  renderBlock({ id: 1, spotify_playlist_url: URL });

  // ссылку не убираем: в embed без входа в Spotify играют только отрывки
  expect(
    screen.getByRole("link", { name: /Открыть плейлист/ }),
  ).toBeInTheDocument();
  // сам плеер живёт во вкладке «Музыка», не здесь
  expect(screen.queryByTitle("Плейлист книги в Spotify")).not.toBeInTheDocument();
});

test("плейлиста ещё нет — есть кнопка создания", () => {
  renderBlock({ id: 1, spotify_playlist_url: null });

  expect(
    screen.getByRole("button", { name: /Создать плейлист/ }),
  ).toBeInTheDocument();
});

test("плеер стоит во вкладке «Музыка» и не грузится на других вкладках", async () => {
  server.use(
    http.get("/api/v1/books/1", () =>
      HttpResponse.json({
        id: 1,
        title: "Волшебная гора",
        author: "Томас Манн",
        status: "read",
        rating: 9,
        spotify_playlist_url: URL,
      }),
    ),
    http.get("/api/v1/books/1/atmosphere/music", () =>
      HttpResponse.json({
        selections: [
          {
            source: "Claude",
            payload: [{ title: "Song A", artist: "Artist A" }],
            explanation: "Тихо",
          },
        ],
      }),
    ),
  );

  renderApp("/books/1");

  expect(await screen.findByText("Song A")).toBeInTheDocument();
  expect(screen.getByTitle("Плейлист книги в Spotify")).toHaveAttribute(
    "src",
    "https://open.spotify.com/embed/playlist/4PHjdTvj7io13Kd5G7d6Ys",
  );

  // на «Угощениях» плеера нет: он играет музыку этой книги, а не всё подряд
  await userEvent.click(screen.getByRole("button", { name: "Угощения" }));
  expect(screen.queryByTitle("Плейлист книги в Spotify")).not.toBeInTheDocument();
});
