import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Building2, Globe, FileText, User, Mail, Lock } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/apiService';
import { createFirebaseAccountOnly, firebaseAuthError } from '../services/authService';
import { toast } from 'sonner';

export function OrgSignup() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();

  // If already logged in, skip the account fields — just create the org
  const isLoggedIn = !!user;

  const [orgName, setOrgName] = useState('');
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [managerName, setManagerName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (!orgName.trim()) { setError('Organisation name is required.'); return; }

    if (!isLoggedIn) {
      if (!managerName.trim()) { setError('Your name is required.'); return; }
      if (password !== confirm) { setError('Passwords do not match.'); return; }
      if (password.length < 6) { setError('Password must be at least 6 characters.'); return; }
    }

    setLoading(true);

    if (!isLoggedIn) {
      try {
        // 1. Create Firebase auth account only — backend writes the Firestore
        //    profile with role=manager so there is no candidate→manager race.
        await createFirebaseAccountOnly(email, password, managerName);
      } catch (err: unknown) {
        const code = (err as { code?: string }).code ?? '';
        setError(firebaseAuthError(code) || (err instanceof Error ? err.message : 'Account creation failed.'));
        setLoading(false);
        return;
      }
    }

    try {
      // 2. Create org — backend sets role=manager + org_id on the user doc
      await api.orgs.create({ name: orgName, website, description });

      // 3. Force-reload AuthContext so the new role/org_id propagates
      await refreshUser();

      toast.success(`Welcome to RecruitSquad, ${orgName}!`);
      navigate('/manager', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Organisation creation failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-sm border w-full max-w-lg p-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
            <Building2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Register Your Company</h1>
            <p className="text-sm text-gray-500">
              {isLoggedIn ? `Signed in as ${user.email}` : 'Set up your organisation and manager account'}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Org section */}
          <div className="space-y-3 pb-4 border-b">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Organisation</p>

            <div className="space-y-1">
              <Label htmlFor="orgName">Company Name *</Label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="orgName"
                  className="pl-9"
                  placeholder="Acme Corp"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="website">Website</Label>
              <div className="relative">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="website"
                  className="pl-9"
                  placeholder="https://acme.com"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="description">Short Description</Label>
              <div className="relative">
                <FileText className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
                <textarea
                  id="description"
                  className="w-full pl-9 pr-3 py-2 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2}
                  placeholder="What does your company do?"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Manager account section — hidden when already logged in */}
          {!isLoggedIn && <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Your Manager Account</p>

            <div className="space-y-1">
              <Label htmlFor="managerName">Full Name *</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="managerName"
                  className="pl-9"
                  placeholder="Jane Smith"
                  value={managerName}
                  onChange={(e) => setManagerName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="email">Work Email *</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="email"
                  type="email"
                  className="pl-9"
                  placeholder="jane@acme.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="password">Password *</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="password"
                    type="password"
                    className="pl-9"
                    placeholder="Min 6 chars"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="confirm">Confirm *</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="confirm"
                    type="password"
                    className="pl-9"
                    placeholder="Repeat password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>
          </div>}

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Creating…' : isLoggedIn ? 'Create Organisation' : 'Create Organisation & Account'}
          </Button>

          {!isLoggedIn && (
            <p className="text-center text-sm text-gray-500">
              Already have an account?{' '}
              <a href="/login" className="text-blue-600 hover:underline">Sign in</a>
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
