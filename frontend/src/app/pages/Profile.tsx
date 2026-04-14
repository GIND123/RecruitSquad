import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { api, MyApplication } from '../services/apiService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { User, Mail, Briefcase, Calendar, FileText, ArrowRight, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

const STAGE_COLOR: Record<string, string> = {
  APPLIED: 'bg-yellow-100 text-yellow-800',
  SOURCED: 'bg-blue-100 text-blue-800',
  OA_SENT: 'bg-purple-100 text-purple-800',
  OA_COMPLETED: 'bg-indigo-100 text-indigo-800',
  SHORTLISTED: 'bg-green-100 text-green-800',
  INTERVIEW: 'bg-orange-100 text-orange-800',
  OFFERED: 'bg-teal-100 text-teal-800',
  REJECTED: 'bg-red-100 text-red-800',
};

export const Profile = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState<MyApplication[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!user) { setIsLoading(false); return; }

    api.jobs.myApplications()
      .then(({ applications }) => setRows(applications))
      .catch(() => toast.error('Failed to load your applications.'))
      .finally(() => setIsLoading(false));
  }, [user]);

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <h1 className="text-2xl font-bold mb-4">Login Required</h1>
          <p className="text-gray-600 mb-6">
            Please login to view your profile and applications.
          </p>
          <Button onClick={() => navigate('/login')}>Go to Login</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-12">
        <div className="container mx-auto px-4">
          <h1 className="text-3xl md:text-4xl font-bold mb-2">My Profile</h1>
          <p className="opacity-90">Manage your applications and profile information</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Profile Info */}
          <div className="lg:col-span-1">
            <Card className="p-6">
              <div className="text-center mb-6">
                <div className="w-24 h-24 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <User className="w-12 h-12 text-white" />
                </div>
                <h2 className="text-xl font-semibold mb-1">{user.name}</h2>
                <p className="text-gray-600 text-sm">{user.role === 'candidate' ? 'Job Seeker' : 'Manager'}</p>
              </div>

              <div className="space-y-4 border-t pt-4">
                <div className="flex items-center gap-3 text-sm">
                  <Mail className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-700">{user.email}</span>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <Briefcase className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-700">{rows.length} Application{rows.length !== 1 ? 's' : ''}</span>
                </div>
              </div>

              <Button className="w-full mt-6" onClick={() => navigate('/jobs')}>
                Browse Jobs
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Card>
          </div>

          {/* Applications */}
          <div className="lg:col-span-2">
            <h2 className="text-2xl font-semibold mb-6">My Applications</h2>

            {isLoading ? (
              <div className="flex justify-center py-16">
                <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : rows.length > 0 ? (
              <div className="space-y-4">
                {rows.map(({ candidate, job }) => (
                  <Card key={candidate.candidate_id} className="p-6 hover:shadow-lg transition-shadow">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <h3 className="text-xl font-semibold">{job.title}</h3>
                          <Badge className={STAGE_COLOR[candidate.pipeline_stage] ?? 'bg-gray-100 text-gray-800'}>
                            {candidate.pipeline_stage.replace(/_/g, ' ')}
                          </Badge>
                        </div>

                        <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
                          <div className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            <span>Applied {new Date(candidate.created_at).toLocaleDateString()}</span>
                          </div>
                          {(candidate as any).resume_filename && (
                            <div className="flex items-center gap-1">
                              <FileText className="w-4 h-4" />
                              <span>{(candidate as any).resume_filename}</span>
                            </div>
                          )}
                        </div>

                        {(candidate as any).resume_url && (
                          <a
                            href={(candidate as any).resume_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            View Resume
                          </a>
                        )}
                      </div>

                      <Button variant="outline" onClick={() => navigate(`/jobs/${job.job_id}`)}>
                        View Job
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="p-12 text-center">
                <Briefcase className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">No Applications Yet</h3>
                <p className="text-gray-600 mb-6">
                  You haven't applied to any jobs yet. Browse our open positions to get started!
                </p>
                <Button onClick={() => navigate('/jobs')}>Explore Jobs</Button>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
