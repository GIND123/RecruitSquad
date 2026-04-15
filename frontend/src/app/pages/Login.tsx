import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { auth } from '../services/firebase';
import { getUserProfile, firebaseAuthError } from '../services/authService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Building2, User, Lock, Eye, EyeOff, Mail } from 'lucide-react';
import { toast } from 'sonner';

type Mode = 'login' | 'signup' | 'forgot';

export const Login = () => {
  const { login, signup, resetPassword } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const nextPath = searchParams.get('next') ?? '/profile';
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<Mode>('login');

  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [signupForm, setSignupForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [forgotEmail, setForgotEmail] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [showSignupPass, setShowSignupPass] = useState(false);

  // After login, check Firestore role and redirect managers to /manager
  const redirectAfterLogin = async () => {
    try {
      const uid = auth.currentUser?.uid;
      if (uid) {
        const profile = await getUserProfile(uid);
        if (profile?.role === 'manager' && profile.org_id) {
          navigate('/manager', { replace: true });
          return;
        }
      }
    } catch {
      // fall through to default redirect
    }
    navigate(nextPath, { replace: true });
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await login(loginForm.email, loginForm.password);
      toast.success('Welcome back!');
      await redirectAfterLogin();
    } catch (err: any) {
      toast.error(firebaseAuthError(err.code));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (signupForm.password !== signupForm.confirm) {
      toast.error('Passwords do not match.');
      return;
    }
    setIsLoading(true);
    try {
      await signup(signupForm.email, signupForm.password, signupForm.name);
      toast.success('Account created! Welcome to RecruitSquad.');
      navigate(nextPath, { replace: true });
    } catch (err: any) {
      toast.error(firebaseAuthError(err.code));
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await resetPassword(forgotEmail);
      toast.success('Password reset email sent! Check your inbox.');
      setMode('login');
    } catch (err: any) {
      toast.error(firebaseAuthError(err.code));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4 py-12">
      <Card className="max-w-md w-full p-8">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Building2 className="w-12 h-12 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Welcome to RecruitSquad</h1>
          <p className="text-gray-600">Sign in to continue</p>
        </div>

        {mode === 'login' && (
          <div className="space-y-4">
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <Label htmlFor="email">Email Address</Label>
                <div className="relative mt-1.5">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={loginForm.email}
                    onChange={(e) => setLoginForm((p) => ({ ...p, email: e.target.value }))}
                    className="pl-10"
                    required
                    autoComplete="email"
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center">
                  <Label htmlFor="password">Password</Label>
                  <button
                    type="button"
                    className="text-xs text-blue-600 hover:underline"
                    onClick={() => setMode('forgot')}
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative mt-1.5">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="password"
                    type={showPass ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={loginForm.password}
                    onChange={(e) => setLoginForm((p) => ({ ...p, password: e.target.value }))}
                    className="pl-10 pr-10"
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    onClick={() => setShowPass((v) => !v)}
                    tabIndex={-1}
                    aria-label={showPass ? 'Hide password' : 'Show password'}
                  >
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                {isLoading ? 'Signing in…' : 'Sign In'}
              </Button>
            </form>

            <p className="text-sm text-center text-gray-600">
              Don't have an account?{' '}
              <button
                type="button"
                className="text-blue-600 hover:underline font-medium"
                onClick={() => setMode('signup')}
              >
                Sign up
              </button>
            </p>
          </div>
        )}

        {mode === 'signup' && (
          <form onSubmit={handleSignup} className="space-y-4">
            <div>
              <Label htmlFor="s-name">Full Name</Label>
              <div className="relative mt-1.5">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="s-name"
                  type="text"
                  placeholder="Jane Smith"
                  value={signupForm.name}
                  onChange={(e) => setSignupForm((p) => ({ ...p, name: e.target.value }))}
                  className="pl-10"
                  required
                  autoComplete="name"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="s-email">Email Address</Label>
              <div className="relative mt-1.5">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="s-email"
                  type="email"
                  placeholder="you@example.com"
                  value={signupForm.email}
                  onChange={(e) => setSignupForm((p) => ({ ...p, email: e.target.value }))}
                  className="pl-10"
                  required
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="s-password">Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="s-password"
                  type={showSignupPass ? 'text' : 'password'}
                  placeholder="Min. 6 characters"
                  value={signupForm.password}
                  onChange={(e) => setSignupForm((p) => ({ ...p, password: e.target.value }))}
                  className="pl-10 pr-10"
                  required
                  minLength={6}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  onClick={() => setShowSignupPass((v) => !v)}
                  tabIndex={-1}
                  aria-label={showSignupPass ? 'Hide password' : 'Show password'}
                >
                  {showSignupPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <Label htmlFor="s-confirm">Confirm Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="s-confirm"
                  type={showSignupPass ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={signupForm.confirm}
                  onChange={(e) => setSignupForm((p) => ({ ...p, confirm: e.target.value }))}
                  className="pl-10"
                  required
                  autoComplete="new-password"
                />
              </div>
            </div>

            <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
              {isLoading ? 'Creating account…' : 'Create Account'}
            </Button>

            <p className="text-sm text-center text-gray-600">
              Already have an account?{' '}
              <button
                type="button"
                className="text-blue-600 hover:underline font-medium"
                onClick={() => setMode('login')}
              >
                Sign in
              </button>
            </p>
          </form>
        )}

        {mode === 'forgot' && (
          <form onSubmit={handleForgotPassword} className="space-y-4">
            <p className="text-sm text-gray-600">
              Enter your email and we'll send you a reset link.
            </p>
            <div>
              <Label htmlFor="f-email">Email Address</Label>
              <div className="relative mt-1.5">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="f-email"
                  type="email"
                  placeholder="you@example.com"
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  className="pl-10"
                  required
                  autoComplete="email"
                />
              </div>
            </div>

            <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
              {isLoading ? 'Sending…' : 'Send Reset Link'}
            </Button>

            <p className="text-sm text-center text-gray-600">
              <button
                type="button"
                className="text-blue-600 hover:underline font-medium"
                onClick={() => setMode('login')}
              >
                ← Back to sign in
              </button>
            </p>
          </form>
        )}
      </Card>
    </div>
  );
};
