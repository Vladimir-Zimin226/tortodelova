import React, { useEffect, useState } from "react";
import { useAuth } from "../providers/AuthProvider";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultMode?: "login" | "register";
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  defaultMode = "login",
}) => {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">(defaultMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setMode(defaultMode);
      setEmail("");
      setPassword("");
      setError(null);
      setLoading(false);
    }
  }, [isOpen, defaultMode]);

  if (!isOpen) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || "Ошибка авторизации");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-backdrop" onClick={onClose}>
      <div
        className="auth-modal"
        onClick={(e) => e.stopPropagation()} // чтобы клик внутри не закрывал модалку
      >
        <button
          type="button"
          className="auth-modal-close"
          onClick={onClose}
          aria-label="Закрыть"
        >
          ✕
        </button>

        <h2 className="auth-modal-title">
          {mode === "login" ? "Вход в Tortodelova" : "Регистрация в Tortodelova"}
        </h2>
        <p className="auth-modal-subtitle">
          {mode === "login"
            ? "Введите почту и пароль, чтобы продолжить генерации и управлять балансом."
            : "Создайте аккаунт, чтобы сохранять свои генерации и пополнять кредиты."}
        </p>

        <div className="auth-modal-tabs">
          <button
            type="button"
            className={`auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => setMode("login")}
          >
            Вход
          </button>
          <button
            type="button"
            className={`auth-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => setMode("register")}
          >
            Регистрация
          </button>
        </div>

        <form className="auth-modal-form" onSubmit={handleSubmit}>
          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
            />
          </label>

          <label className="auth-field">
            <span>Пароль</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Минимум 6 символов"
            />
          </label>

          {error && <div className="auth-modal-error">{error}</div>}

          <button
            type="submit"
            className="btn-primary auth-modal-submit"
            disabled={loading}
          >
            {loading
              ? "Подождите..."
              : mode === "login"
              ? "Войти"
              : "Создать аккаунт"}
          </button>
        </form>
      </div>
    </div>
  );
};
