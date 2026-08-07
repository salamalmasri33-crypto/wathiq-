import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { NotificationsProvider } from "@/contexts/NotificationsContext";
import { useAuth } from "@/contexts/AuthContext";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { MainLayout } from "@/components/layout/MainLayout";
import {
  ADD_DOCUMENT_ALLOWED_ROLES,
  DEPARTMENTS_ALLOWED_ROLES,
  DASHBOARD_ALLOWED_ROLES,
  DOCUMENTS_ALLOWED_ROLES,
  EDIT_DOCUMENT_ALLOWED_ROLES,
  getHomeRoute,
  INSTITUTION_SETTINGS_ALLOWED_ROLES,
  MAINTENANCE_ALLOWED_ROLES,
  MY_DOCUMENTS_ALLOWED_ROLES,
  NOTIFICATIONS_ALLOWED_ROLES,
  REPORTS_ALLOWED_ROLES,
  USERS_ALLOWED_ROLES,
} from "@/lib/roles";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Unauthorized from "./pages/Unauthorized";
import NotFound from "./pages/NotFound";
import { MyDocuments } from "./pages/MyDocuments";
import { Documents } from "./pages/Documents";
import { AddDocument } from "./pages/AddDocument";
import { DocumentView } from "./pages/DocumentView";
import { Search } from "./pages/Search";
import { Reports } from "./pages/Reports";
import  Settings  from "./pages/Settings";
import { Users } from "./pages/Users";
import { DocumentEdit } from "./pages/DocumentEdit";
import { Notifications } from "./pages/Notifications";
import { Departments } from "./pages/Departments";
import { InstitutionSettings } from "./pages/InstitutionSettings";
import { Maintenance } from "./pages/Maintenance";

const queryClient = new QueryClient();

const RootRedirect = () => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return null;
  }

  return <Navigate to={isAuthenticated ? getHomeRoute(user) : "/login"} replace />;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <LanguageProvider>
      <AuthProvider>
        <NotificationsProvider>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<RootRedirect />} />
                <Route path="/login" element={<Login />} />
                <Route path="/unauthorized" element={<Unauthorized />} />

                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute allowedRoles={DASHBOARD_ALLOWED_ROLES}>
                      <MainLayout>
                        <Dashboard />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/my-documents"
                  element={
                    <ProtectedRoute allowedRoles={MY_DOCUMENTS_ALLOWED_ROLES}>
                      <MainLayout>
                        <MyDocuments />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/documents"
                  element={
                    <ProtectedRoute allowedRoles={DOCUMENTS_ALLOWED_ROLES}>
                      <MainLayout>
                        <Documents />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/add-document"
                  element={
                    <ProtectedRoute allowedRoles={ADD_DOCUMENT_ALLOWED_ROLES}>
                      <MainLayout>
                        <AddDocument />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/documents/:id"
                  element={
                    <ProtectedRoute>
                      <MainLayout>
                        <DocumentView />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/documents/:id/edit"
                  element={
                    <ProtectedRoute allowedRoles={EDIT_DOCUMENT_ALLOWED_ROLES}>
                      <MainLayout>
                        <DocumentEdit />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/search"
                  element={
                    <ProtectedRoute>
                      <MainLayout>
                        <Search />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/reports"
                  element={
                    <ProtectedRoute allowedRoles={REPORTS_ALLOWED_ROLES}>
                      <MainLayout>
                        <Reports />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/notifications"
                  element={
                    <ProtectedRoute allowedRoles={NOTIFICATIONS_ALLOWED_ROLES}>
                      <MainLayout>
                        <Notifications />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/permissions"
                  element={
                    <ProtectedRoute>
                      <Navigate to="/settings" replace />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/settings"
                  element={
                    <ProtectedRoute>
                      <MainLayout>
                        <Settings />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/departments"
                  element={
                    <ProtectedRoute allowedRoles={DEPARTMENTS_ALLOWED_ROLES}>
                      <MainLayout>
                        <Departments />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/institution-settings"
                  element={
                    <ProtectedRoute allowedRoles={INSTITUTION_SETTINGS_ALLOWED_ROLES}>
                      <MainLayout>
                        <InstitutionSettings />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/maintenance"
                  element={
                    <ProtectedRoute allowedRoles={MAINTENANCE_ALLOWED_ROLES}>
                      <MainLayout>
                        <Maintenance />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/users"
                  element={
                    <ProtectedRoute allowedRoles={USERS_ALLOWED_ROLES}>
                      <MainLayout>
                        <Users />
                      </MainLayout>
                    </ProtectedRoute>
                  }
                />

                <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </TooltipProvider>
        </NotificationsProvider>
      </AuthProvider>
    </LanguageProvider>
  </QueryClientProvider>
);

export default App;
