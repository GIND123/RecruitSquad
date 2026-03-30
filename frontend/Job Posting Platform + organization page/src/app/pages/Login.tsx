import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Building2, User, Lock } from 'lucide-react';
import { toast } from 'sonner';

export const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  
  const [managerForm, setManagerForm] = useState({
    email: '',
    password: ''
  });

  const [candidateForm, setCandidateForm] = useState({
    email: ''
  });

  const handleManagerLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    const success = await login(managerForm.email, managerForm.password, 'manager');
    
    setIsLoading(false);

    if (success) {
      toast.success('Welcome back!');
      navigate('/manager');
    } else {
      toast.error('Invalid credentials. Try: manager@google.com / password');
    }
  };

  const handleCandidateLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    const success = await login(candidateForm.email, '', 'candidate');
    
    setIsLoading(false);

    if (success) {
      toast.success('Welcome!');
      navigate('/profile');
    } else {
      toast.error('Failed to login. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4 py-12">
      <Card className="max-w-md w-full p-8">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Building2 className="w-12 h-12 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Welcome to Google Careers</h1>
          <p className="text-gray-600">Login to continue</p>
        </div>

        <Tabs defaultValue="candidate" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="candidate">Candidate</TabsTrigger>
            <TabsTrigger value="manager">Manager</TabsTrigger>
          </TabsList>
          
          <TabsContent value="candidate">
            <form onSubmit={handleCandidateLogin} className="space-y-4">
              <div>
                <Label htmlFor="candidate-email">Email Address</Label>
                <div className="relative mt-1.5">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="candidate-email"
                    type="email"
                    placeholder="your.email@example.com"
                    value={candidateForm.email}
                    onChange={(e) => setCandidateForm({ email: e.target.value })}
                    className="pl-10"
                    required
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Enter any email to continue as a candidate
                </p>
              </div>

              <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                {isLoading ? 'Logging in...' : 'Continue as Candidate'}
              </Button>
            </form>
          </TabsContent>
          
          <TabsContent value="manager">
            <form onSubmit={handleManagerLogin} className="space-y-4">
              <div>
                <Label htmlFor="manager-email">Email Address</Label>
                <div className="relative mt-1.5">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="manager-email"
                    type="email"
                    placeholder="manager@google.com"
                    value={managerForm.email}
                    onChange={(e) => setManagerForm({ ...managerForm, email: e.target.value })}
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="manager-password">Password</Label>
                <div className="relative mt-1.5">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="manager-password"
                    type="password"
                    placeholder="••••••••"
                    value={managerForm.password}
                    onChange={(e) => setManagerForm({ ...managerForm, password: e.target.value })}
                    className="pl-10"
                    required
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Demo credentials: manager@google.com / password
                </p>
              </div>

              <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                {isLoading ? 'Logging in...' : 'Login as Manager'}
              </Button>
            </form>
          </TabsContent>
        </Tabs>

        <div className="mt-6 pt-6 border-t text-center">
          <p className="text-sm text-gray-600">
            Don't have an account?{' '}
            <button 
              className="text-blue-600 hover:underline font-medium"
              onClick={() => navigate('/jobs')}
            >
              Browse jobs first
            </button>
          </p>
        </div>
      </Card>
    </div>
  );
};
