// Выпадающее меню шапки (задача 110).
//
// ⚠ Здесь НЕТ `useFocusTrap`, хотя в задаче он был помечен как «не забыть».
// Ловушка нужна модальным окнам, которые перекрывают страницу и не дают
// работать с остальным. Меню немодально: Tab из него обязан уводить дальше
// по странице, иначе клавиатурный пользователь запирается в четырёх пунктах
// и не может добраться до поиска. Из ловушки здесь взято только полезное —
// Esc закрывает и ВОЗВРАЩАЕТ фокус на кнопку (иначе он улетает в body,
// и следующий Tab начинает обход страницы заново).
import { useEffect, useId, useRef, useState } from "react";

// `align` — к какому краю КНОПКИ прижимается панель.
// «left» для меню в середине ряда (панель раскрывается вправо, под своей
// кнопкой), «right» — для крайнего правого, иначе панель уехала бы за экран.
function DropdownMenu({ label, title, children, className = "", align = "left" }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;

    function onKeyDown(e) {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    // Клик мимо меню закрывает его. Слушаем именно `mousedown`, а не `click`:
    // по `click` меню успевало закрыться до того, как срабатывал переход
    // по ссылке внутри него, и пункт «проглатывался».
    function onPointerDown(e) {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  return (
    <div className={"menu " + className} ref={rootRef}>
      <button
        ref={buttonRef}
        className="btn-ghost menu-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        title={title}
      >
        {label}
        <span className="menu-caret" aria-hidden="true">
          ▾
        </span>
      </button>

      {open && (
        <div
          className={"menu-panel menu-panel-" + align}
          id={menuId}
          role="menu"
          // клик по любому пункту закрывает меню: пункты — это ссылки и кнопки
          // действий, после них оставаться в открытом меню незачем
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export default DropdownMenu;
