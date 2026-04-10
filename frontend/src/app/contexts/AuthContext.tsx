import React, { createContext, useContext, useState, useEffect } from 'react';

interface User {
  id: string;
  email: string;
  name: string;
  role: 'candidate' | 'manager';
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string, role: 'candidate' | 'manager') => Promise<boolean>;
  logout: () => void;
  isManager: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // Check for existing session
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }
  }, []);

  const login = async (email: string, password: string, role: 'candidate' | 'manager'): Promise<boolean> => {
    // Mock authentication
    // Manager login: manager@google.com / password
    // Candidate can use any email
    
    if (role === 'manager' && email === 'manager@google.com' && password === 'password') {
      const newUser: User = {
        id: 'manager-1',
        email,
        name: 'Hiring Manager',
        role: 'manager'
      };
      setUser(newUser);
      localStorage.setItem('user', JSON.stringify(newUser));
      return true;
    } else if (role === 'candidate') {
      const newUser: User = {
        id: `candidate-${Date.now()}`,
        email,
        name: email.split('@')[0],
        role: 'candidate'
      };
      setUser(newUser);
      localStorage.setItem('user', JSON.stringify(newUser));
      return true;
    }
    
    return false;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('user');
  };

  const isManager = user?.role === 'manager';

  return (
    <AuthContext.Provider value={{ user, login, logout, isManager }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
