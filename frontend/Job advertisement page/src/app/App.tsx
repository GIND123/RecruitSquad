import { useState } from "react";
import { Search, SlidersHorizontal, MapPin, X } from "lucide-react";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { JobCard, type Job } from "./components/JobCard";
import { JobDetail } from "./components/JobDetail";
import { JobFilters } from "./components/JobFilters";

// Mock job data
const mockJobs: Job[] = [
  {
    id: "1",
    title: "Senior Software Engineer",
    company: "Google",
    location: "Mountain View, CA",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: "2 days ago",
    applicants: 127,
    description: "Join our world-class engineering team to build innovative products that impact billions of users worldwide.",
    promoted: true,
  },
  {
    id: "2",
    title: "Product Manager",
    company: "Microsoft",
    location: "Redmond, WA",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: "5 days ago",
    applicants: 89,
    description: "Lead product strategy and execution for cutting-edge cloud solutions.",
  },
  {
    id: "3",
    title: "UX Designer",
    company: "Apple",
    location: "Cupertino, CA",
    type: "Full-time",
    level: "Associate",
    postedDate: "1 week ago",
    applicants: 203,
    description: "Create beautiful and intuitive user experiences for millions of Apple users.",
  },
  {
    id: "4",
    title: "Data Scientist",
    company: "Amazon",
    location: "Seattle, WA",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: "3 days ago",
    applicants: 156,
    description: "Drive data-driven decision making through advanced analytics and machine learning.",
  },
  {
    id: "5",
    title: "Frontend Developer",
    company: "Meta",
    location: "Menlo Park, CA",
    type: "Full-time",
    level: "Entry level",
    postedDate: "4 days ago",
    applicants: 94,
    description: "Build the next generation of social experiences with modern web technologies.",
  },
  {
    id: "6",
    title: "DevOps Engineer",
    company: "Netflix",
    location: "Los Gatos, CA",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: "1 week ago",
    applicants: 72,
    description: "Manage infrastructure and deployment pipelines for streaming to millions of users.",
  },
  {
    id: "7",
    title: "Marketing Manager",
    company: "Tesla",
    location: "Palo Alto, CA",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: "6 days ago",
    applicants: 118,
    description: "Drive brand awareness and customer engagement for sustainable energy products.",
  },
  {
    id: "8",
    title: "Mobile Developer",
    company: "Uber",
    location: "San Francisco, CA",
    type: "Full-time",
    level: "Associate",
    postedDate: "2 days ago",
    applicants: 85,
    description: "Create seamless mobile experiences for riders and drivers around the world.",
  },
  {
    id: "9",
    title: "Security Engineer",
    company: "Cisco",
    location: "San Jose, CA",
    type: "Full-time",
    level: "Mid-Senior level",
    postedDate: "1 week ago",
    applicants: 61,
    description: "Protect critical infrastructure and ensure the security of enterprise systems.",
  },
  {
    id: "10",
    title: "Business Analyst",
    company: "Salesforce",
    location: "San Francisco, CA",
    type: "Full-time",
    level: "Associate",
    postedDate: "4 days ago",
    applicants: 102,
    description: "Analyze business processes and drive insights to improve customer success.",
  },
];

function App() {
  const [selectedJob, setSelectedJob] = useState<Job>(mockJobs[0]);
  const [showFilters, setShowFilters] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [locationQuery, setLocationQuery] = useState("");

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex-shrink-0">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
                <span className="text-white font-bold">in</span>
              </div>
              <h1 className="font-semibold hidden sm:block">LinkedIn Jobs</h1>
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
            {mockJobs.length} jobs
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
            {mockJobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onClick={() => setSelectedJob(job)}
                isActive={selectedJob.id === job.id}
              />
            ))}
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
                  onClick={() => setSelectedJob(mockJobs[0])}
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

export default App;
