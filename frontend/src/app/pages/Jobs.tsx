import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { api, JobDetail, JobSummary } from '../services/apiService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Search, MapPin, Clock, ArrowRight, DollarSign, X } from 'lucide-react';
import { toast } from 'sonner';

const OPEN_STATUSES = new Set(['PENDING', 'SOURCING', 'SOURCED', 'ACTIVE', 'SCHEDULING', 'SCHEDULED']);

type TimeFilter = 'any' | '24h' | '7d';

const TIME_OPTIONS: { value: TimeFilter; label: string }[] = [
  { value: 'any', label: 'Any time' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d',  label: 'Last 7 days' },
];

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export const Jobs = () => {
  const [jobs, setJobs] = useState<JobDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('any');
  const [selectedOrg, setSelectedOrg] = useState('');

  useEffect(() => {
    api.jobs
      .list()
      .then(async (summaries: JobSummary[]) => {
        const open = summaries.filter((j) => OPEN_STATUSES.has(j.status));
        const details = await Promise.all(
          open.map((j) => api.jobs.get(j.job_id).catch(() => j as JobDetail))
        );
        setJobs(details);
      })
      .catch(() => toast.error('Failed to load jobs.'))
      .finally(() => setIsLoading(false));
  }, []);

  const orgList = useMemo(
    () => Array.from(new Set(jobs.map((j) => j.team).filter(Boolean))).sort() as string[],
    [jobs]
  );

  // Count per org for the badge
  const orgCounts = useMemo(
    () => Object.fromEntries(orgList.map((org) => [org, jobs.filter((j) => j.team === org).length])),
    [jobs, orgList]
  );

  const filtered = useMemo(() => {
    const now = Date.now();
    const cutoff: Record<TimeFilter, number> = {
      any: 0,
      '24h': now - 24 * 60 * 60 * 1000,
      '7d':  now - 7 * 24 * 60 * 60 * 1000,
    };
    const q = searchTerm.toLowerCase();

    return jobs.filter((j) => {
      if (q && !j.title.toLowerCase().includes(q) && !j.team?.toLowerCase().includes(q)) return false;
      if (selectedOrg && j.team !== selectedOrg) return false;
      if (timeFilter !== 'any' && new Date(j.created_at).getTime() < cutoff[timeFilter]) return false;
      return true;
    });
  }, [jobs, searchTerm, selectedOrg, timeFilter]);

  const hasFilters = searchTerm || selectedOrg || timeFilter !== 'any';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-14">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl md:text-5xl font-bold mb-2">Find Your Dream Job</h1>
          <p className="text-lg opacity-90 mb-8">
            Explore {jobs.length} open positions across our global offices
          </p>

          <div className="flex flex-col sm:flex-row gap-3 max-w-4xl">
            {/* Search */}
            <div className="flex-1 bg-white/95 rounded-full py-2.5 px-4 flex items-center gap-2 shadow-sm">
              <Search className="w-4 h-4 text-gray-400 shrink-0" />
              <Input
                type="text"
                placeholder="Search by job title or company..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="border-0 focus-visible:ring-0 text-gray-900 bg-transparent p-0 h-auto"
              />
            </div>

            {/* Time filter */}
            <div className="flex items-center bg-white/20 backdrop-blur-sm rounded-full p-1 gap-0.5 shrink-0">
              {TIME_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setTimeFilter(value)}
                  className={`px-4 py-1.5 text-sm font-medium rounded-full transition-all whitespace-nowrap ${
                    timeFilter === value
                      ? 'bg-white text-purple-700 shadow-sm'
                      : 'text-white/80 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">

        {/* Top alignment row */}
        <div className="flex gap-6 items-center mb-3">
          <div className="w-52 shrink-0 hidden md:flex items-center">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Department</p>
          </div>
          <div className="flex-1 flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm text-gray-500">
                {filtered.length} result{filtered.length !== 1 ? 's' : ''}
              </p>
              {selectedOrg && (
                <span className="inline-flex items-center gap-1 text-xs bg-purple-100 text-purple-700 rounded-full px-2.5 py-1 font-medium">
                  {selectedOrg}
                  <button onClick={() => setSelectedOrg('')}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
            </div>
            {hasFilters && (
              <button
                onClick={() => { setSearchTerm(''); setSelectedOrg(''); setTimeFilter('any'); }}
                className="text-sm text-purple-600 hover:underline"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        <div className="flex gap-6 items-start">

          {/* Sidebar */}
          <aside className="w-52 shrink-0 hidden md:block sticky top-20">
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <ul>
                <li className="border-b border-gray-50">
                  <button
                    onClick={() => setSelectedOrg('')}
                    className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors ${
                      selectedOrg === ''
                        ? 'bg-purple-50 text-purple-700 font-semibold'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <span>All</span>
                    <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${
                      selectedOrg === '' ? 'bg-purple-100 text-purple-600' : 'bg-gray-100 text-gray-400'
                    }`}>
                      {jobs.length}
                    </span>
                  </button>
                </li>
                {orgList.map((org, i) => (
                  <li key={org} className={i < orgList.length - 1 ? 'border-b border-gray-50' : ''}>
                    <button
                      onClick={() => setSelectedOrg(org === selectedOrg ? '' : org)}
                      className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors ${
                        selectedOrg === org
                          ? 'bg-purple-50 text-purple-700 font-semibold'
                          : 'text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      <span className="truncate text-left pr-2">{org}</span>
                      <span className={`text-xs rounded-full px-2 py-0.5 font-medium shrink-0 ${
                        selectedOrg === org ? 'bg-purple-100 text-purple-600' : 'bg-gray-100 text-gray-400'
                      }`}>
                        {orgCounts[org]}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </aside>

          {/* Main results */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4 md:hidden">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm text-gray-500">
                  {filtered.length} result{filtered.length !== 1 ? 's' : ''}
                </p>
                {selectedOrg && (
                  <span className="inline-flex items-center gap-1 text-xs bg-purple-100 text-purple-700 rounded-full px-2.5 py-1 font-medium">
                    {selectedOrg}
                    <button onClick={() => setSelectedOrg('')}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )}
              </div>
              {hasFilters && (
                <button
                  onClick={() => { setSearchTerm(''); setSelectedOrg(''); setTimeFilter('any'); }}
                  className="text-sm text-purple-600 hover:underline"
                >
                  Clear all
                </button>
              )}
            </div>

            {isLoading ? (
              <div className="flex justify-center py-16">
                <div className="w-8 h-8 border-4 border-purple-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : filtered.length === 0 ? (
              <Card className="p-12 text-center">
                <p className="text-gray-500 text-lg">No open positions match your filters.</p>
              </Card>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {filtered.map((job) => {
                  const location = job.locations?.join(', ') || 'Remote';
                  const salary =
                    job.budget_min && job.budget_max
                      ? `$${(job.budget_min / 1000).toFixed(0)}k – $${(job.budget_max / 1000).toFixed(0)}k`
                      : null;
                  return (
                    <Card
                      key={job.job_id}
                      className="p-5 hover:shadow-md transition-shadow cursor-pointer"
                      onClick={() => navigate(`/jobs/${job.job_id}`)}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <h2 className="text-lg font-bold text-gray-900 leading-snug">{job.title}</h2>
                          {job.team && (
                            <p className="text-xs text-gray-400 mt-0.5">{job.team}</p>
                          )}

                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-sm text-gray-500">
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3.5 h-3.5" />
                              {location}
                            </span>
                            {salary && (
                              <span className="flex items-center gap-1 text-green-700">
                                <DollarSign className="w-3.5 h-3.5" />
                                {salary}
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5" />
                              {timeAgo(job.created_at)}
                            </span>
                          </div>

                          {job.role_description && (
                            <p className="text-sm text-gray-500 mt-2 line-clamp-2">
                              {job.role_description}
                            </p>
                          )}
                        </div>

                        <Button
                          className="shrink-0 self-start sm:self-center"
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
      </div>
    </div>
  );
};
