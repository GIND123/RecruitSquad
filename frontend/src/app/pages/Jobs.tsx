import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { api, JobDetail, JobSummary } from '../services/apiService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Search, MapPin, Briefcase, Calendar, ArrowRight, DollarSign, Users } from 'lucide-react';
import { toast } from 'sonner';

const OPEN_STATUSES = new Set(['PENDING', 'SOURCING', 'SOURCED', 'ACTIVE', 'SCHEDULING', 'SCHEDULED']);

export const Jobs = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    api.jobs.list()
      .then(async (summaries) => {
        const open = summaries.filter((j) => OPEN_STATUSES.has(j.status));
        // Fetch full detail for each job to get locations + salary
        const details = await Promise.all(open.map((j) => api.jobs.get(j.job_id).catch(() => j as JobDetail)));
        setJobs(details);
      })
      .catch(() => toast.error('Failed to load jobs.'))
      .finally(() => setIsLoading(false));
  }, []);

  const filtered = jobs.filter((j) =>
    j.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-16">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">Find Your Dream Job</h1>
          <p className="text-lg opacity-90 mb-8">
            Explore {jobs.length} open position{jobs.length !== 1 ? 's' : ''}
          </p>

          <div className="bg-white rounded-lg p-2 flex flex-col md:flex-row gap-2 max-w-3xl">
            <div className="flex-1 flex items-center gap-2 px-3">
              <Search className="w-5 h-5 text-gray-400" />
              <Input
                type="text"
                placeholder="Search by job title..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="border-0 focus-visible:ring-0 text-gray-900"
              />
            </div>
            <Button size="lg" className="md:w-auto">Search Jobs</Button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <Card className="p-12 text-center">
            <p className="text-gray-500 text-lg">No open positions found.</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {filtered.map((job) => {
              const location = job.locations?.join(', ') || 'Remote';
              const salary = job.budget_min && job.budget_max
                ? `$${(job.budget_min / 1000).toFixed(0)}k – $${(job.budget_max / 1000).toFixed(0)}k`
                : null;
              return (
                <Card
                  key={job.job_id}
                  className="p-6 hover:shadow-lg transition-shadow cursor-pointer"
                  onClick={() => navigate(`/jobs/${job.job_id}`)}
                >
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <h2 className="text-xl font-semibold">{job.title}</h2>
                        {job.team && (
                          <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                            {job.team}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm text-gray-600 mt-2">
                        <div className="flex items-center gap-1">
                          <MapPin className="w-4 h-4" />
                          <span>{location}</span>
                        </div>
                        {salary && (
                          <div className="flex items-center gap-1 text-green-700">
                            <DollarSign className="w-4 h-4" />
                            <span>{salary}</span>
                          </div>
                        )}
                        <div className="flex items-center gap-1">
                          <Users className="w-4 h-4" />
                          <span>{job.headcount} opening{job.headcount !== 1 ? 's' : ''}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-4 h-4" />
                          <span>Posted {new Date(job.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      {job.role_description && (
                        <p className="text-sm text-gray-500 mt-3 line-clamp-2">
                          {job.role_description}
                        </p>
                      )}
                    </div>
                    <Button
                      className="shrink-0"
                      onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${job.job_id}`); }}
                    >
                      View Details
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
