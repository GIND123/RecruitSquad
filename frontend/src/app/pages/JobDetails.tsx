import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api, JobDetail } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import { MapPin, Briefcase, Calendar, DollarSign, ArrowLeft, LogIn } from 'lucide-react';
import { toast } from 'sonner';

export const JobDetails = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, firebaseUser } = useAuth();
  const isLoggedIn = !!user || !!firebaseUser;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api.jobs.get(id)
      .then(setJob)
      .catch(() => toast.error('Failed to load job details.'))
      .finally(() => setIsLoading(false));
  }, [id]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold mb-4">Job Not Found</h1>
        <Button onClick={() => navigate('/jobs')}>Back to Jobs</Button>
      </div>
    );
  }

  const salaryRange = job.budget_min && job.budget_max
    ? `$${job.budget_min.toLocaleString()} – $${job.budget_max.toLocaleString()}`
    : null;

  const location = job.locations?.join(', ') || 'Remote';
  const expRange = `${job.experience_min}–${job.experience_max} years`;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-8">
        <div className="container mx-auto px-4">
          <Button
            variant="ghost"
            className="text-white hover:bg-white/20 mb-4"
            onClick={() => navigate('/jobs')}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Jobs
          </Button>

          <h1 className="text-3xl md:text-4xl font-bold mb-4">{job.title}</h1>

          <div className="flex flex-wrap gap-6 text-sm opacity-90">
            {job.team && (
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4" />
                <span>{job.team}</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4" />
              <span>{location}</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <span>Posted {new Date(job.created_at).toLocaleDateString()}</span>
            </div>
            {salaryRange && (
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                <span>{salaryRange}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="p-6">
              <h2 className="text-2xl font-semibold mb-4">About the Role</h2>
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                {job.role_description}
              </p>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <Card className="p-6 sticky top-24">
              <h3 className="text-xl font-semibold mb-4">Ready to Apply?</h3>
              <p className="text-gray-600 mb-6 text-sm">
                Submit your application and our team will review it shortly.
              </p>

              {isLoggedIn ? (
                <Button
                  className="w-full mb-3"
                  size="lg"
                  onClick={() => navigate(`/jobs/${job.job_id}/apply`)}
                >
                  Apply Now
                </Button>
              ) : (
                <Button
                  className="w-full mb-3"
                  size="lg"
                  variant="outline"
                  onClick={() => navigate(`/login?next=/jobs/${job.job_id}/apply`)}
                >
                  <LogIn className="w-4 h-4 mr-2" />
                  Sign in to Apply
                </Button>
              )}

              <Separator className="my-4" />

              <div className="space-y-3 text-sm">
                {job.team && (
                  <div>
                    <p className="text-gray-500 mb-1">Team</p>
                    <p className="font-medium">{job.team}</p>
                  </div>
                )}
                <div>
                  <p className="text-gray-500 mb-1">Location</p>
                  <p className="font-medium">{location}</p>
                </div>
                <div>
                  <p className="text-gray-500 mb-1">Experience</p>
                  <p className="font-medium">{expRange}</p>
                </div>
                <div>
                  <p className="text-gray-500 mb-1">Headcount</p>
                  <p className="font-medium">{job.headcount} position{job.headcount !== 1 ? 's' : ''}</p>
                </div>
                {salaryRange && (
                  <div>
                    <p className="text-gray-500 mb-1">Salary Range</p>
                    <p className="font-medium text-green-600">{salaryRange}</p>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};
