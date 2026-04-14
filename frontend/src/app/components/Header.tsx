import { Link, useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Building2, User, LogOut } from 'lucide-react';

export const Header = () => {
  const { user, firebaseUser, loading, logout, isManager } = useAuth();
  const navigate = useNavigate();

  // Show the authenticated UI as soon as Firebase confirms the session,
  // even if the Firestore profile fetch is still in flight.
  const isLoggedIn = !!user || !!firebaseUser;
  const displayName =
    user?.name ??
    firebaseUser?.displayName ??
    firebaseUser?.email?.split('@')[0] ??
    'User';

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <Building2 className="w-8 h-8 text-blue-600" />
          <div>
            <h1 className="font-semibold text-xl">RecruitSquad</h1>
            <p className="text-xs text-gray-500">Careers</p>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link to="/jobs" className="text-gray-700 hover:text-gray-900">
            Jobs
          </Link>
          {isLoggedIn && (
            <Link to="/profile" className="text-gray-700 hover:text-gray-900">
              My Applications
            </Link>
          )}
          {isManager && (
            <Link to="/manager" className="text-gray-700 hover:text-gray-900">
              Manager Dashboard
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3">
          {loading ? (
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          ) : isLoggedIn ? (
            <>
              <Link
                to="/profile"
                className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
              >
                <User className="w-4 h-4 text-gray-600" />
                <span className="text-sm">{displayName}</span>
              </Link>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => navigate('/login')}>
              Login
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};
