import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { firebaseAuthError } from '../services/authService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Building2, User, Lock, Eye, EyeOff, Mail } from 'lucide-react';
import { toast } from 'sonner';

type CandidateMode = 'login' | 'signup' | 'forgot';

const GoogleIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      fill="#4285F4"
    />
    <path
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      fill="#34A853"
    />
    <path
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
      fill="#FBBC05"
    />
    <path
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      fill="#EA4335"
    />
  </svg>
);

export const Login = () => {
  const { login, signup, loginWithGoogle, resetPassword } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const nextPath = searchParams.get('next') ?? '/profile';
  const [isLoading, setIsLoading] = useState(false);
  const [candidateMode, setCandidateMode] = useState<CandidateMode>('login');

  // Candidate login/signup fields
  const [candidateLogin, setCandidateLogin] = useState({ email: '', password: '' });
  const [candidateSignup, setCandidateSignup] = useState({
    name: '',
    email: '',
    password: '',
    confirm: '',
  });
  const [forgotEmail, setForgotEmail] = useState('');
  const [showCandidatePass, setShowCandidatePass] = useState(false);
  const [showSignupPass, setShowSignupPass] = useState(false);

  // Manager login fields
  const [managerForm, setManagerForm] = useState({ email: '', password: '' });
  const [showManagerPass, setShowManagerPass] = useState(false);

  const handleCandidateLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await login(candidateLogin.email, candidateLogin.password);
      toast.success('Welcome back!');
      navigate(nextPath);
    } catch (err: any) {
      toast.error(firebaseAuthError(err.code));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCandidateSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (candidateSignup.password !== candidateSignup.confirm) {
      toast.error('Passwords do not match.');
      return;
    }
    setIsLoading(true);
    try {
      await signup(candidateSignup.email, candidateSignup.password, candidateSignup.name);
      toast.success('Account created! Welcome to RecruitSquad.');
      navigate(nextPath);
    } catch (err: any) {
      toast.error(firebaseAuthError(err.code));
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    try {
      await loginWithGoogle();
      toast.success('Signed in with Google!');
      navigate(nextPath);
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
      setCandidateMode('login');
    } catch (err: any) {
      toast.error(firebaseAuthError(err.code));
    } finally {
      setIsLoading(false);
    }
  };

  const handleManagerLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await login(managerForm.email, managerForm.password);
      toast.success('Welcome back!');
      navigate('/manager');
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

        <Tabs defaultValue="candidate" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="candidate">Candidate</TabsTrigger>
            <TabsTrigger value="manager">Manager</TabsTrigger>
          </TabsList>

          {/* ── CANDIDATE TAB ── */}
          <TabsContent value="candidate">
            {candidateMode === 'login' && (
              <div className="space-y-4">
                {/* Google sign-in */}
                <Button
                  type="button"
                  variant="outline"
                  className="w-full flex items-center gap-2"
                  onClick={handleGoogleSignIn}
                  disabled={isLoading}
                >
                  <GoogleIcon />
                  Continue with Google
                </Button>

                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-xs text-gray-400">or</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                <form onSubmit={handleCandidateLogin} className="space-y-4">
                  {/* Email */}
                  <div>
                    <Label htmlFor="c-email">Email Address</Label>
                    <div className="relative mt-1.5">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        id="c-email"
                        type="email"
                        placeholder="you@example.com"
                        value={candidateLogin.email}
                        onChange={(e) =>
                          setCandidateLogin((p) => ({ ...p, email: e.target.value }))
                        }
                        className="pl-10"
                        required
                        autoComplete="email"
                      />
                    </div>
                  </div>

                  {/* Password */}
                  <div>
                    <div className="flex justify-between items-center">
                      <Label htmlFor="c-password">Password</Label>
                      <button
                        type="button"
                        className="text-xs text-blue-600 hover:underline"
                        onClick={() => setCandidateMode('forgot')}
                      >
                        Forgot password?
                      </button>
                    </div>
                    <div className="relative mt-1.5">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        id="c-password"
                        type={showCandidatePass ? 'text' : 'password'}
                        placeholder="••••••••"
                        value={candidateLogin.password}
                        onChange={(e) =>
                          setCandidateLogin((p) => ({ ...p, password: e.target.value }))
                        }
                        className="pl-10 pr-10"
                        required
                        autoComplete="current-password"
                      />
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        onClick={() => setShowCandidatePass((v) => !v)}
                        tabIndex={-1}
                        aria-label={showCandidatePass ? 'Hide password' : 'Show password'}
                      >
                        {showCandidatePass ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
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
                    onClick={() => setCandidateMode('signup')}
                  >
                    Sign up
                  </button>
                </p>
              </div>
            )}

            {candidateMode === 'signup' && (
              <form onSubmit={handleCandidateSignup} className="space-y-4">
                {/* Name */}
                <div>
                  <Label htmlFor="s-name">Full Name</Label>
                  <div className="relative mt-1.5">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="s-name"
                      type="text"
                      placeholder="Jane Smith"
                      value={candidateSignup.name}
                      onChange={(e) =>
                        setCandidateSignup((p) => ({ ...p, name: e.target.value }))
                      }
                      className="pl-10"
                      required
                      autoComplete="name"
                    />
                  </div>
                </div>

                {/* Email */}
                <div>
                  <Label htmlFor="s-email">Email Address</Label>
                  <div className="relative mt-1.5">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="s-email"
                      type="email"
                      placeholder="you@example.com"
                      value={candidateSignup.email}
                      onChange={(e) =>
                        setCandidateSignup((p) => ({ ...p, email: e.target.value }))
                      }
                      className="pl-10"
                      required
                      autoComplete="email"
                    />
                  </div>
                </div>

                {/* Password */}
                <div>
                  <Label htmlFor="s-password">Password</Label>
                  <div className="relative mt-1.5">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="s-password"
                      type={showSignupPass ? 'text' : 'password'}
                      placeholder="Min. 6 characters"
                      value={candidateSignup.password}
                      onChange={(e) =>
                        setCandidateSignup((p) => ({ ...p, password: e.target.value }))
                      }
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
                      {showSignupPass ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Confirm password */}
                <div>
                  <Label htmlFor="s-confirm">Confirm Password</Label>
                  <div className="relative mt-1.5">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="s-confirm"
                      type={showSignupPass ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={candidateSignup.confirm}
                      onChange={(e) =>
                        setCandidateSignup((p) => ({ ...p, confirm: e.target.value }))
                      }
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
                    onClick={() => setCandidateMode('login')}
                  >
                    Sign in
                  </button>
                </p>
              </form>
            )}

            {candidateMode === 'forgot' && (
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
                    onClick={() => setCandidateMode('login')}
                  >
                    ← Back to sign in
                  </button>
                </p>
              </form>
            )}
          </TabsContent>

          {/* ── MANAGER TAB ── */}
          <TabsContent value="manager">
            <form onSubmit={handleManagerLogin} className="space-y-4">
              <div>
                <Label htmlFor="m-email">Email Address</Label>
                <div className="relative mt-1.5">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="m-email"
                    type="email"
                    placeholder="manager@company.com"
                    value={managerForm.email}
                    onChange={(e) => setManagerForm((p) => ({ ...p, email: e.target.value }))}
                    className="pl-10"
                    required
                    autoComplete="email"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="m-password">Password</Label>
                <div className="relative mt-1.5">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="m-password"
                    type={showManagerPass ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={managerForm.password}
                    onChange={(e) => setManagerForm((p) => ({ ...p, password: e.target.value }))}
                    className="pl-10 pr-10"
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    onClick={() => setShowManagerPass((v) => !v)}
                    tabIndex={-1}
                    aria-label={showManagerPass ? 'Hide password' : 'Show password'}
                  >
                    {showManagerPass ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Manager accounts are provisioned by your admin.
                </p>
              </div>

              <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                {isLoading ? 'Signing in…' : 'Sign In as Manager'}
              </Button>
            </form>
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
};
