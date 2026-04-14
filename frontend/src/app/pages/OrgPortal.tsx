import { useNavigate } from 'react-router';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { User, Building2 } from 'lucide-react';

export const OrgPortal = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4 py-12">
      <div className="max-w-xl w-full text-center">
        <h1 className="text-3xl font-bold mb-3 text-gray-900">Welcome to RecruitSquad</h1>
        <p className="text-gray-600 mb-10">How would you like to sign in?</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <Card
            className="p-8 flex flex-col items-center gap-4 hover:shadow-lg transition-shadow cursor-pointer"
            onClick={() => navigate('/login?tab=candidate')}
          >
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
              <User className="w-8 h-8 text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold mb-1">Candidate Login</h2>
              <p className="text-sm text-gray-500">
                Track your applications and complete assessments.
              </p>
            </div>
            <Button className="w-full mt-2" onClick={() => navigate('/login?tab=candidate')}>
              Sign In as Candidate
            </Button>
          </Card>

          <Card
            className="p-8 flex flex-col items-center gap-4 hover:shadow-lg transition-shadow cursor-pointer"
            onClick={() => navigate('/login?tab=manager')}
          >
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center">
              <Building2 className="w-8 h-8 text-purple-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold mb-1">Manager Login</h2>
              <p className="text-sm text-gray-500">
                Post jobs, review candidates, and manage your pipeline.
              </p>
            </div>
            <Button
              className="w-full mt-2"
              variant="outline"
              onClick={() => navigate('/login?tab=manager')}
            >
              Sign In as Manager
            </Button>
          </Card>
        </div>

        <p className="text-sm text-gray-500 mt-8">
          Not your organization?{' '}
          <button
            type="button"
            className="text-blue-600 hover:underline font-medium"
            onClick={() => navigate('/org-register')}
          >
            Go back
          </button>
        </p>
      </div>
    </div>
  );
};
