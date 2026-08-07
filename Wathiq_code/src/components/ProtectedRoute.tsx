import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { hasAnyRole } from '@/lib/roles';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: readonly string[];
}

export const ProtectedRoute = ({ children, allowedRoles }: ProtectedRouteProps) => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user && !hasAnyRole(user, allowedRoles)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};
