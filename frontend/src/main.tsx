import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { auth } from "./api";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/ui";
import "./index.css";
import AuthPage from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import PaperPage from "./pages/Paper";
import Planner from "./pages/Planner";
import PredictionsPage from "./pages/Predictions";
import SubjectsPage from "./pages/Subjects";
import UploadPage from "./pages/Upload";
import Workspace from "./pages/Workspace";

function RequireAuth({ children }: { children: JSX.Element }) {
  const loc = useLocation();
  if (!auth.token()) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return children;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route path="/app" element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Dashboard />} />
            <Route path="subjects" element={<SubjectsPage />} />
            <Route path="subjects/:id" element={<Workspace />} />
            <Route path="subjects/:id/predictions" element={<PredictionsPage />} />
            <Route path="papers/:id" element={<PaperPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="planner" element={<Planner />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
