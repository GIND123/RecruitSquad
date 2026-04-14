import { Navigate, useLocation } from 'react-router';
import { useAuth } from '../contexts/AuthContext';

interface Props {
  children: React.ReactNode;
  requireManager?: boolean;
}

export const ProtectedRoute: React.FC<Props> = ({ children, requireManager = false }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (requireManager && user.role !== 'manager') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
