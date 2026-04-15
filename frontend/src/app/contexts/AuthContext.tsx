import React, { createContext, useContext, useState, useEffect } from 'react';
import { onAuthStateChanged, User as FirebaseUser } from 'firebase/auth';
import { auth } from '../services/firebase';
import {
  getUserProfile,
  loginWithEmail,
  signupWithEmail,
  logoutUser,
  resetPassword as fbResetPassword,
  UserProfile,
} from '../services/authService';

interface AuthContextType {
  user: UserProfile | null;
  firebaseUser: FirebaseUser | null;
  loading: boolean;
  isManager: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
      setLoading(true);
      setFirebaseUser(fbUser);
      if (fbUser) {
        try {
          const profile = await getUserProfile(fbUser.uid);
          if (profile) {
            setUser(profile);
          } else {
            // Profile doc doesn't exist yet — race condition on fresh signup or
            // Google sign-in (Firestore write happens after onAuthStateChanged fires).
            // Use Firebase user as immediate fallback so the header updates at once.
            setUser({
              uid: fbUser.uid,
              email: fbUser.email ?? '',
              name:
                fbUser.displayName ??
                fbUser.email?.split('@')[0] ??
                'User',
              role: 'candidate',
              createdAt: new Date().toISOString(),
            });
            // Retry once after 500 ms so we pick up the real Firestore doc
            // (which includes the correct role for manager accounts).
            setTimeout(async () => {
              try {
                const retried = await getUserProfile(fbUser.uid);
                if (retried) setUser(retried);
              } catch {
                /* keep fallback */
              }
            }, 500);
          }
        } catch {
          setUser(null);
        }
      } else {
        setUser(null);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const login = async (email: string, password: string) => {
    await loginWithEmail(email, password);
    // onAuthStateChanged will update user state
  };

  const signup = async (email: string, password: string, name: string) => {
    await signupWithEmail(email, password, name);
  };

  const logout = async () => {
    await logoutUser();
  };

  const resetPassword = async (email: string) => {
    await fbResetPassword(email);
  };

  const refreshUser = async () => {
    if (!firebaseUser) return;
    try {
      const profile = await getUserProfile(firebaseUser.uid);
      if (profile) setUser(profile);
    } catch {
      /* keep existing user */
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        firebaseUser,
        loading,
        isManager: user?.role === 'manager',
        login,
        signup,
        logout,
        resetPassword,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};
