import { useEffect, useState } from "react";
import { Search, SlidersHorizontal, MapPin, X } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { JobCard, type Job } from "../components/JobCard";
import { JobDetail } from "../components/JobDetail";
import { JobFilters } from "../components/JobFilters";
import { api, JobSummary } from "../services/apiService";
import { toast } from "sonner";

const OPEN_STATUSES = new Set(['PENDING', 'SOURCING', 'SOURCED', 'ACTIVE', 'SCHEDULING', 'SCHEDULED']);

function summaryToJob(j: JobSummary): Job {
  return {
    id: j.job_id,
    title: j.title,
    company: j.org_name || "RecruitSquad",
    location: "See details",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: new Date(j.created_at).toLocaleDateString(),
    applicants: j.candidate_count,
    description: `${j.headcount} opening${j.headcount !== 1 ? 's' : ''}`,
  };
}

export function JobAdvertisements() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [locationQuery, setLocationQuery] = useState("");

  useEffect(() => {
    api.jobs.list()
      .then((summaries) => {
        const open = summaries.filter((j) => OPEN_STATUSES.has(j.status));
        const mapped = open.map(summaryToJob);
        setJobs(mapped);
        if (mapped.length > 0) setSelectedJob(mapped[0]);
      })
      .catch(() => toast.error('Failed to load jobs.'))
      .finally(() => setIsLoading(false));
  }, []);

  const filtered = jobs.filter((j) => {
    const matchesSearch = j.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLocation = !locationQuery || j.location.toLowerCase().includes(locationQuery.toLowerCase());
    return matchesSearch && matchesLocation;
  });

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex-shrink-0">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
                <span className="text-white font-bold text-xs">RS</span>
              </div>
              <h1 className="font-semibold hidden sm:block">RecruitSquad Jobs</h1>
            </div>

            <div className="flex-1 flex gap-2">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search jobs"
                  className="pl-10"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="relative flex-1 max-w-xs hidden md:block">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Location"
                  className="pl-10"
                  value={locationQuery}
                  onChange={(e) => setLocationQuery(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Sub-header */}
      <div className="bg-white border-b px-4 py-2 flex-shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className="gap-2"
            >
              <SlidersHorizontal className="w-4 h-4" />
              <span className="hidden sm:inline">All filters</span>
              <span className="sm:hidden">Filters</span>
            </Button>
          </div>

          <p className="text-sm text-gray-600">
            <span className="hidden sm:inline">Showing </span>
            {isLoading ? '…' : filtered.length} job{filtered.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        <div className="max-w-7xl mx-auto h-full flex">
          {/* Filters Sidebar (Desktop) */}
          {showFilters && (
            <div className="hidden lg:block w-64 flex-shrink-0">
              <JobFilters onClose={() => setShowFilters(false)} />
            </div>
          )}

          {/* Mobile Filters Overlay */}
          {showFilters && (
            <div className="lg:hidden fixed inset-0 bg-black/50 z-40" onClick={() => setShowFilters(false)}>
              <div className="w-80 h-full bg-white" onClick={(e) => e.stopPropagation()}>
                <JobFilters onClose={() => setShowFilters(false)} />
              </div>
            </div>
          )}

          {/* Job List */}
          <div className="w-full lg:w-96 flex-shrink-0 bg-white border-r overflow-y-auto">
            {isLoading ? (
              <div className="flex justify-center py-16">
                <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <p>No open positions found.</p>
              </div>
            ) : (
              filtered.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onClick={() => setSelectedJob(job)}
                  isActive={selectedJob?.id === job.id}
                />
              ))
            )}
          </div>

          {/* Job Detail (Desktop) */}
          <div className="hidden lg:block flex-1 overflow-hidden">
            {selectedJob && <JobDetail job={selectedJob} />}
          </div>

          {/* Job Detail (Mobile) */}
          {selectedJob && (
            <div className="lg:hidden fixed inset-0 bg-white z-30 overflow-y-auto">
              <div className="sticky top-0 bg-white border-b p-4 flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSelectedJob(filtered[0] ?? null)}
                >
                  <X className="w-5 h-5" />
                </Button>
                <h2 className="font-semibold">Job Details</h2>
              </div>
              <JobDetail job={selectedJob} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
