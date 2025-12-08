import React, { useState } from "react";
import { Link, useNavigate, Outlet } from "react-router-dom";
import { useAuth } from "../providers/AuthProvider";
import { AuthModal } from "./AuthModal";
import { ProfileModal } from "./ProfileModal";

export const MainLayout: React.FC = () => {
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <header className="topbar">
        <div
          className="topbar-left"
          onClick={() => navigate("/")}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              navigate("/");
            }
          }}
        >
          <span className="logo">tortodelova</span>
        </div>

        <nav className="topbar-nav" aria-label="Основная навигация">
          <Link to="/">О сервисе</Link>
          <Link to="/app">Попробовать</Link>
          {isAdmin && (
            <Link to="/admin" className="btn-secondary">
              Управлять
            </Link>
          )}
        </nav>

        <div className="topbar-right">
          {isAuthenticated && user ? (
            <>
              <button
                type="button"
                className="user-email"
                onClick={() => setProfileModalOpen(true)}
                title={user.email}
              >
                {user.email}
              </button>
              <button
                className="btn-outline"
                onClick={() => {
                  setProfileModalOpen(false);
                  logout();
                }}
              >
                Выйти
              </button>
            </>
          ) : (
            <button
              className="btn-primary"
              onClick={() => setAuthModalOpen(true)}
            >
              Войти
            </button>
          )}
        </div>
      </header>

      <main className="main-content">
        <Outlet />
      </main>

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
      />

      <ProfileModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
      />
    </>
  );
};
