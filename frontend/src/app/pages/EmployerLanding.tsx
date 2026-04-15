import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Building2, Plus, LogIn, Globe } from 'lucide-react';
import { Button } from '../components/ui/button';
import { useAuth } from '../contexts/AuthContext';
import { api, OrgSummary } from '../services/apiService';
import { toast } from 'sonner';

export function EmployerLanding() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [orgs, setOrgs] = useState<OrgSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // If the user is already a manager with an org, send them straight to the dashboard
  useEffect(() => {
    if (user?.role === 'manager' && user.org_id) {
      navigate('/manager', { replace: true });
    }
  }, [user, navigate]);

  useEffect(() => {
    api.orgs.list()
      .then((res) => setOrgs(res.orgs))
      .catch(() => toast.error('Failed to load organisations.'))
      .finally(() => setLoading(false));
  }, []);


  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-16 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-blue-600 rounded-2xl mb-6">
            <Building2 className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Hire with AI, faster</h1>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-8">
            RecruitSquad automates sourcing, screening, and interviews so your team focuses on the best candidates.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button size="lg" onClick={() => navigate('/employer/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Register Your Company
            </Button>
            {!user && (
              <Button size="lg" variant="outline" onClick={() => navigate('/login')}>
                <LogIn className="w-4 h-4 mr-2" />
                Sign In
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Org list */}
      <div className="max-w-5xl mx-auto px-4 py-12">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">Companies on RecruitSquad</h2>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : orgs.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Building2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p>No companies yet. Be the first!</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {orgs.map((org) => (
              <div key={org.org_id} className="bg-white rounded-xl border p-5 flex flex-col gap-3 hover:shadow-sm transition-shadow">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Building2 className="w-5 h-5 text-blue-600" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-gray-900 truncate">{org.name}</h3>
                    {org.website && (
                      <a
                        href={org.website}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-blue-500 hover:underline flex items-center gap-1 mt-0.5"
                      >
                        <Globe className="w-3 h-3" />
                        {org.website.replace(/^https?:\/\//, '')}
                      </a>
                    )}
                  </div>
                </div>

                {org.description && (
                  <p className="text-sm text-gray-500 line-clamp-2">{org.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
