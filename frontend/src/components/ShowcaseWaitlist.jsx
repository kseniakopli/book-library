// Лист ожидания на публичной витрине (28.07).
//
// Тот же приёмник, что у лендинга — Formspree (landing/index.html). Своего
// эндпоинта сознательно не заводим: хранить чужие почты у себя — это база,
// выгрузка, удаление по просьбе и ответственность за персональные данные
// ради одного поля ввода.
//
// ⚠ Прод: адрес Formspree должен быть в `connect-src` CSP (backend/main.py),
// иначе браузер молча заблокирует отправку. Локально Vite отдаёт страницу
// без CSP, поэтому ошибка вылезла бы только после деплоя.
import { useState } from "react";

const FORMSPREE_URL = "https://formspree.io/f/xnjevbzd";
const CONTACT_EMAIL = "nctrnlib@gmail.com";

function ShowcaseWaitlist() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState(null); // {ok: boolean, text: string}
  const [sending, setSending] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSending(true);
    setStatus(null);
    try {
      const body = new FormData();
      body.append("email", email);
      const response = await fetch(FORMSPREE_URL, {
        method: "POST",
        body,
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        setStatus({ ok: true, text: "Готово! Напишу, когда открою доступ." });
        setEmail("");
      } else {
        setStatus({
          ok: false,
          text: "Не получилось отправить. Попробуйте ещё раз или напишите на почту.",
        });
      }
    } catch {
      setStatus({
        ok: false,
        text: "Нет связи. Попробуйте ещё раз или напишите на почту.",
      });
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="showcase-waitlist" aria-labelledby="waitlist-heading">
      <h2 className="showcase-section-title" id="waitlist-heading">
        Хотите попробовать?
      </h2>
      <p className="showcase-waitlist-lead">
        Сервис в разработке. Оставьте почту — напишу, когда открою доступ.
      </p>

      <form className="showcase-waitlist-form" onSubmit={submit}>
        <label className="visually-hidden" htmlFor="waitlist-email">
          Ваша почта
        </label>
        <input
          id="waitlist-email"
          type="email"
          name="email"
          required
          placeholder="ваша@почта.ru"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button className="add-btn" type="submit" disabled={sending}>
          {sending ? "Отправляю…" : "Хочу попробовать"}
        </button>
      </form>

      {status && (
        <p
          className={status.ok ? "showcase-form-ok" : "error"}
          role="status"
          aria-live="polite"
        >
          {status.text}
        </p>
      )}

      <p className="muted showcase-waitlist-note">
        Или просто напишите: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
      </p>
    </section>
  );
}

export default ShowcaseWaitlist;
