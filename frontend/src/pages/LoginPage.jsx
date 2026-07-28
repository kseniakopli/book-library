// Вход в сервис (этап 9). Единственный экран, доступный без авторизации.
//
// Своей формы с паролем нет: пароли проверяет Google, мы только уводим к нему.
// Инвайт-код нужен ТОЛЬКО при первом входе — сервис тратит платные AI-вызовы,
// поэтому регистрация по приглашению. Уже знакомый аккаунт входит без кода.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import "../styles/login.css";

// Причины отказа приходят от бэкенда в ?error= (routers/auth.py)
const ERRORS = {
  need_invite: "Это первый вход с этого аккаунта — нужен код приглашения.",
  bad_invite: "Такого кода приглашения нет. Проверьте, нет ли опечатки.",
  invite_used: "Этот код уже использован. Попросите новый.",
  cancelled: "Вход отменён.",
  bad_state: "Ссылка входа устарела — попробуйте ещё раз.",
  google_failed: "Google не подтвердил вход. Попробуйте ещё раз.",
  oauth_not_configured: "Вход через Google пока не настроен на сервере.",
};

function LoginPage() {
  const [invite, setInvite] = useState("");
  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");

  const status = useQuery({
    queryKey: ["auth", "status"],
    queryFn: api.getAuthStatus,
    retry: false,
  });
  const oauthReady = status.data?.oauth_configured !== false;

  return (
    <main className="login">
      <div className="login-card">
        <h1 className="login-title">nocturne</h1>
        <p className="login-subtitle">Атмосферные литературные вечера</p>

        {error && <p className="error login-error">{ERRORS[error] || "Не удалось войти."}</p>}

        {/* форма, а не просто поле: Enter в коде приглашения = «Войти» */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (oauthReady) window.location.href = api.loginUrl(invite);
          }}
        >
          <label className="login-label" htmlFor="invite">
            Код приглашения
            <span className="login-hint"> — только для первого входа</span>
          </label>
          <input
            id="invite"
            className="login-input"
            value={invite}
            onChange={(e) => setInvite(e.target.value)}
            placeholder="XXXX-XXXX-XXXX"
            autoComplete="off"
          />

          {oauthReady && (
            // ссылка, а не fetch: браузер должен УЙТИ на страницу согласия Google
            <a className="add-btn login-btn" href={api.loginUrl(invite)}>
              Войти через Google
            </a>
          )}
        </form>

        {!oauthReady && (
          <p className="muted">
            Вход через Google не настроен. Задайте ключи GOOGLE_OAUTH_* на сервере.
          </p>
        )}

        <p className="login-note">
          Пароль вводится на стороне Google — мы его не видим и не храним.
        </p>
      </div>
    </main>
  );
}

export default LoginPage;
