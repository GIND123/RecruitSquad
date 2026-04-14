import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Building2, Mail, Globe } from 'lucide-react';
import { toast } from 'sonner';

export const OrgRegister = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [form, setForm] = useState({
    orgName: '',
    email: '',
    website: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate registration — replace with real API call when backend endpoint exists
    await new Promise((r) => setTimeout(r, 600));
    setIsLoading(false);
    toast.success(`Welcome, ${form.orgName}! Choose how to continue.`);
    navigate('/org-portal');
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4 py-12">
      <Card className="max-w-md w-full p-8">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Building2 className="w-12 h-12 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Organization Sign-In</h1>
          <p className="text-gray-600 text-sm">
            Register your organization to access candidate management and job posting tools.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <Label htmlFor="org-name">Organization Name</Label>
            <div className="relative mt-1.5">
              <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="org-name"
                type="text"
                placeholder="Acme Corp"
                value={form.orgName}
                onChange={(e) => setForm((p) => ({ ...p, orgName: e.target.value }))}
                className="pl-10"
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="org-email">Work Email</Label>
            <div className="relative mt-1.5">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="org-email"
                type="email"
                placeholder="hr@yourcompany.com"
                value={form.email}
                onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                className="pl-10"
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="org-website">
              Website <span className="text-gray-400 font-normal">(optional)</span>
            </Label>
            <div className="relative mt-1.5">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="org-website"
                type="url"
                placeholder="https://yourcompany.com"
                value={form.website}
                onChange={(e) => setForm((p) => ({ ...p, website: e.target.value }))}
                className="pl-10"
              />
            </div>
          </div>

          <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
            {isLoading ? 'Continuing…' : 'Continue'}
          </Button>
        </form>

        <p className="text-sm text-center text-gray-500 mt-6">
          Looking to apply for a job?{' '}
          <button
            type="button"
            className="text-blue-600 hover:underline font-medium"
            onClick={() => navigate('/jobs')}
          >
            Browse openings
          </button>
        </p>
      </Card>
    </div>
  );
};
