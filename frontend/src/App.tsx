import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { MainLayout } from "./components/MainLayout";
import { LandingPage } from "./pages/LandingPage";
import { ChatPage } from "./pages/ChatPage";
import { AdminPage } from "./pages/AdminPage";
import { useAuth } from "./providers/AuthProvider";

const AdminRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { isAdmin, loading } = useAuth();
  if (loading) return <div style={{ padding: 24 }}>Загрузка...</div>;
  if (!isAdmin) return <Navigate to="/" replace />;
  return children;
};

export const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="app" element={<ChatPage />} />
        <Route
          path="admin"
          element={
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          }
        />
      </Route>
    </Routes>
  );
};