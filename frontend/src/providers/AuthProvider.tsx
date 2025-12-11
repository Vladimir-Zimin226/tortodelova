import React, { createContext, useContext, useEffect, useState } from "react";
import type { UserProfile } from "../types/api";
import {
  getMeProfile,
  login as apiLogin,
  register as apiRegister,
  setAuthToken,
  claimDemoPrediction,
} from "../api/client";

interface AuthContextValue {
  user: UserProfile | null;
  loading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string): Promise<void>;
  logout(): void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const DEMO_TASK_ID_KEY = "demoTaskId";
const DEMO_PROMPT_KEY = "demoPrompt";

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // При загрузке — пробуем вытащить профиль по токену из cookie
  useEffect(() => {
    (async () => {
      try {
        const me = await getMeProfile();
        setUser(me);
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleLogin = async (email: string, password: string) => {
    const tokenResp = await apiLogin(email, password);
    setAuthToken(tokenResp.access_token);

    const me = await getMeProfile();
    setUser(me);

    // Пробуем привязать демо-предсказание к только что залогиненному пользователю
    const demoTaskId = localStorage.getItem(DEMO_TASK_ID_KEY);
    if (demoTaskId) {
      try {
        await claimDemoPrediction(demoTaskId);
        // после успешной привязки очищаем локальное состояние демо
        localStorage.removeItem(DEMO_TASK_ID_KEY);
        localStorage.removeItem(DEMO_PROMPT_KEY);
      } catch (e) {
        // не критично, просто логируем
        console.error("Failed to claim demo prediction", e);
      }
    }
  };

  const handleRegister = async (email: string, password: string) => {
    await apiRegister(email, password);
    // сразу логинимся теми же данными
    await handleLogin(email, password);
  };

  const handleLogout = () => {
    setAuthToken(undefined);
    setUser(null);
  };

  const value: AuthContextValue = {
    user,
    loading,
    isAuthenticated: !!user,
    isAdmin: user?.role === "admin",
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}