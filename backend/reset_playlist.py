"""Сброс ссылки на Spotify-плейлист у книги.

Зачем: `POST /books/{id}/playlist` не пересоздаёт существующий плейлист —
возвращает сохранённую ссылку. Чтобы собрать плейлист заново (например, после
фикса поиска треков 20.07), ссылку нужно обнулить.

Сам плейлист в Spotify скрипт НЕ трогает — удалите его руками в приложении,
иначе останется висеть в вашем профиле.

Запуск из папки backend/:
    python reset_playlist.py 42        # по id книги
    python reset_playlist.py --all     # у всех книг сразу
    python reset_playlist.py --list    # показать, у кого есть плейлисты
"""

import sys

from sqlmodel import Session, col, select

import database
from models import Book


def _books_with_playlist(session: Session) -> list[Book]:
    return session.exec(
        select(Book).where(col(Book.spotify_playlist_url).is_not(None))
    ).all()


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    with Session(database.engine) as session:
        if args[0] == "--list":
            books = _books_with_playlist(session)
            for book in books:
                print(f"{book.id:>4}  {book.title} — {book.author}")
            print(f"Всего с плейлистами: {len(books)}")
            return

        if args[0] == "--all":
            books = _books_with_playlist(session)
        else:
            book = session.get(Book, int(args[0]))
            if book is None:
                print(f"Книга {args[0]} не найдена")
                return
            if book.spotify_playlist_url is None:
                print(f"У книги «{book.title}» плейлиста и так нет")
                return
            books = [book]

        for book in books:
            print(f"Сбрасываю: {book.title} ({book.spotify_playlist_url})")
            book.spotify_playlist_url = None
            session.add(book)
        session.commit()
        print(f"Готово: {len(books)}. Плейлисты в Spotify удалите руками.")


if __name__ == "__main__":
    main()
