import { Link, useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Building2, User, LogOut, Briefcase } from 'lucide-react';

export const Header = () => {
  const { user, logout, isManager } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <Building2 className="w-8 h-8 text-blue-600" />
          <div>
            <h1 className="font-semibold text-xl">Google</h1>
            <p className="text-xs text-gray-500">Careers</p>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link to="/jobs" className="text-gray-700 hover:text-gray-900">
            Jobs
          </Link>
          {user && (
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
          {user ? (
            <>
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full">
                <User className="w-4 h-4 text-gray-600" />
                <span className="text-sm">{user.name}</span>
              </div>
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
