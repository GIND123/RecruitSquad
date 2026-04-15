import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { api, JobSummary } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Plus, Briefcase, Users, Clock, CheckCircle2,
  RefreshCw, ChevronRight, Calendar
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_COLOR: Record<string, string> = {
  PENDING:    'bg-yellow-100 text-yellow-800',
  SOURCING:   'bg-blue-100 text-blue-800',
  SOURCED:    'bg-indigo-100 text-indigo-800',
  ACTIVE:     'bg-green-100 text-green-800',
  SCHEDULING: 'bg-teal-100 text-teal-800',
  SCHEDULED:  'bg-cyan-100 text-cyan-800',
  FAILED:     'bg-red-100 text-red-800',
  CLOSED:     'bg-gray-100 text-gray-700',
};

export const ManagerDashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await api.jobs.list(user?.org_id);
      setJobs(data);
    } catch (err: any) {
      toast.error(err.message ?? 'Failed to load jobs.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, [user?.org_id]);

  const activeJobs      = jobs.filter((j) => ['ACTIVE', 'SCHEDULING', 'SCHEDULED'].includes(j.status));
  const sourcingJobs    = jobs.filter((j) => ['PENDING', 'SOURCING', 'SOURCED'].includes(j.status));
  const totalCandidates = jobs.reduce((sum, j) => sum + (j.candidate_count ?? 0), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-12">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl md:text-4xl font-bold">Manager Dashboard</h1>
              <p className="opacity-80 mt-1">
                {user?.org_name ? `${user.org_name} · ` : ''}Welcome, {user?.name}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="bg-white/10 border-white/30 text-white hover:bg-white/20" onClick={load}>
                <RefreshCw className="w-4 h-4 mr-2" /> Refresh
              </Button>
              <Button variant="secondary" size="lg" onClick={() => navigate('/manager/create-job')}>
                <Plus className="w-5 h-5 mr-2" /> Post New Job
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Jobs',         value: jobs.length,       icon: <Briefcase className="w-6 h-6 text-blue-600" />,   bg: 'bg-blue-50' },
            { label: 'Active / Scheduling', value: activeJobs.length,   icon: <CheckCircle2 className="w-6 h-6 text-green-600" />, bg: 'bg-green-50' },
            { label: 'Sourcing',           value: sourcingJobs.length, icon: <Clock className="w-6 h-6 text-yellow-600" />,     bg: 'bg-yellow-50' },
            { label: 'Total Candidates',   value: totalCandidates,   icon: <Users className="w-6 h-6 text-purple-600" />,      bg: 'bg-purple-50' },
          ].map(({ label, value, icon, bg }) => (
            <Card key={label} className="p-5">
              <div className="flex items-center gap-3">
                <div className={`w-11 h-11 ${bg} rounded-lg flex items-center justify-center`}>
                  {icon}
                </div>
                <div>
                  <p className="text-2xl font-bold">{value}</p>
                  <p className="text-xs text-gray-500">{label}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Job list */}
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <Card className="p-16 text-center">
            <Briefcase className="w-16 h-16 text-gray-200 mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">No Jobs Yet</h3>
            <p className="text-gray-500 mb-6">Post your first job to start the autonomous recruiting pipeline.</p>
            <Button onClick={() => navigate('/manager/create-job')}>
              <Plus className="w-4 h-4 mr-2" /> Post New Job
            </Button>
          </Card>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-500 font-medium">
              All Jobs ({jobs.length}) — click a row to view candidates & pipeline
            </p>
            {jobs.map((job) => (
              <Card
                key={job.job_id}
                className="p-5 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/manager/jobs/${job.job_id}`)}
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h3 className="text-lg font-semibold truncate">{job.title}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[job.status] ?? 'bg-gray-100 text-gray-700'}`}>
                        {job.status}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5" />
                        {job.candidate_count} candidates sourced
                      </span>
                      <span className="flex items-center gap-1">
                        <Briefcase className="w-3.5 h-3.5" />
                        Headcount: {job.headcount}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        {new Date(job.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <Badge variant="outline" className="hidden sm:inline-flex">
                      View Pipeline
                    </Badge>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
