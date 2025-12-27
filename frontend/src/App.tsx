import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./state/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { LogoutPage } from "./pages/LogoutPage";
import { RoleHome } from "./pages/RoleHome";

export const App: React.FC = () => {
  const { booted, user } = useAuth();

  if (!booted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-50">
        <p className="text-slate-300">Loading…</p>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/logout" element={<LogoutPage />} />
      <Route path="/" element={user ? <RoleHome /> : <Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
