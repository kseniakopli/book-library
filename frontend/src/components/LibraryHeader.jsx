import { Link } from "react-router-dom";
import { useAuth, useLogout } from "../hooks/useAuth";
import DropdownMenu from "./DropdownMenu";

// Шапка главной (задача 110: разделы вместо ряда из семи кнопок).
//
// Структура (решение Ксении 02.08):
//   «Книги»  → авторы (жанры добавятся в з.112);
//   чип ЛК   → рекомендации, статистика, импорт, экспорт, выход;
//   иконками остаются тема и вид полки — ими переключают часто,
//   прятать частое действие в меню значит менять один клик на два;
//   «+ Добавить книгу» — главное действие страницы, всегда снаружи.
//
// ⚠ Меню одинаковые на всех ширинах, бургера нет (решение Ксении): одна
// логика — одно место, где может разъехаться вёрстка.
function LibraryHeader({
  compact,
  symbolMode,
  onToggleMode,
  theme,
  onToggleTheme,
  csv,
  onAddBook,
  addButtonRef,
}) {
  const { user, isAdmin } = useAuth();
  const logout = useLogout();

  return (
    <header className={"header" + (compact ? " header-compact" : "")}>
      <div>
        <h1 className="title">Библиотека</h1>
        <p className="subtitle">Атмосферные литературные вечера</p>
      </div>

      <div className="header-actions">
        <DropdownMenu label="Книги" title="Разделы библиотеки">
          <Link className="menu-item" to="/authors" role="menuitem">
            Авторы
          </Link>
          <Link className="menu-item" to="/genres" role="menuitem">
            Жанры
          </Link>
        </DropdownMenu>

        <button
          className="btn-ghost icon-btn"
          onClick={onToggleMode}
          title="Как показывать полку"
          aria-label={`Вид полки: ${symbolMode ? "символы" : "обложки"}. Переключить`}
        >
          {symbolMode ? "◈" : "▦"}
        </button>

        <button
          className="btn-ghost icon-btn theme-toggle"
          onClick={onToggleTheme}
          aria-pressed={theme === "dark"}
          aria-label={
            theme === "dark" ? "Включить светлую тему" : "Включить вечернюю тему"
          }
          title={theme === "dark" ? "Светлая тема" : "Вечерняя тема"}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>

        {/* Скрытый input живёт СНАРУЖИ меню: пункт «Импорт CSV» кликает его
            программно, а меню к этому моменту уже закрыто — внутри панели
            input размонтировался бы вместе с ней, и диалог выбора файла
            не открылся бы вовсе. */}
        <input
          type="file"
          accept=".csv"
          ref={csv.inputRef}
          onChange={csv.onFileChange}
          className="file-input-hidden"
          aria-label="Файл CSV для импорта"
        />

        {/* Этап 9: кто вошёл. Аватар из Google — просто картинка по ссылке.
            Чип стал кнопкой меню: личные действия собраны под именем. */}
        {user && (
          <DropdownMenu
            className="menu-account"
            align="right"
            title={user.email || ""}
            label={
              <>
                {user.avatar_url && (
                  <img className="user-avatar" src={user.avatar_url} alt="" />
                )}
                <span className="user-name">
                  {user.display_name}
                  {isAdmin && <span className="user-role"> · админ</span>}
                </span>
              </>
            }
          >
            <Link className="menu-item" to="/recommendations" role="menuitem">
              Рекомендации
            </Link>
            <Link className="menu-item" to="/stats" role="menuitem">
              Статистика
            </Link>

            <div className="menu-sep" role="separator" />

            <button
              className="menu-item"
              onClick={csv.trigger}
              disabled={csv.importing}
              role="menuitem"
            >
              {csv.importing ? "Импортирую…" : "Импорт CSV"}
            </button>
            {/* Задача 35: выгрузка — обычная ссылка, а не fetch: браузер сам
                приложит куку сессии и сохранит файл по Content-Disposition. */}
            <a
              className="menu-item"
              href="/api/v1/export/shelf.csv"
              download
              role="menuitem"
            >
              Экспорт CSV
            </a>

            {/* задача 113: служебный раздел — только админу */}
            {isAdmin && (
              <>
                <div className="menu-sep" role="separator" />
                <Link className="menu-item" to="/admin/data" role="menuitem">
                  Заполнение данных
                </Link>
              </>
            )}

            <div className="menu-sep" role="separator" />

            <button
              className="menu-item menu-item-quiet"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              role="menuitem"
            >
              Выйти
            </button>
          </DropdownMenu>
        )}

        {/* Главное действие — ПОСЛЕДНИМ (решение Ксении 03.08).
            Стояло между «Книги» и личным меню и разрывало их: акцентная
            заливка тяжелее соседей, и ряд читался как две несвязанные группы.
            Теперь навигация идёт подряд, а действие завершает строку. */}
        <button className="add-btn" onClick={onAddBook} ref={addButtonRef}>
          + Добавить книгу
        </button>
      </div>
    </header>
  );
}

export default LibraryHeader;
