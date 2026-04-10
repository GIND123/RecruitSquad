import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useJobs } from '../contexts/JobContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Search, MapPin, Briefcase, Calendar, ArrowRight } from 'lucide-react';

export const Jobs = () => {
  const { jobs } = useJobs();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');

  const activeJobs = jobs.filter(job => job.status === 'active');

  const filteredJobs = activeJobs.filter(job => {
    const matchesSearch = job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         job.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDepartment = selectedDepartment === 'all' || job.department === selectedDepartment;
    return matchesSearch && matchesDepartment;
  });

  const departments = ['all', ...Array.from(new Set(activeJobs.map(job => job.department)))];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-16">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Find Your Dream Job
          </h1>
          <p className="text-lg opacity-90 mb-8">
            Explore {activeJobs.length} open positions across our global offices
          </p>
          
          {/* Search Bar */}
          <div className="bg-white rounded-lg p-2 flex flex-col md:flex-row gap-2 max-w-3xl">
            <div className="flex-1 flex items-center gap-2 px-3">
              <Search className="w-5 h-5 text-gray-400" />
              <Input
                type="text"
                placeholder="Search by job title or keyword..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="border-0 focus-visible:ring-0 text-gray-900"
              />
            </div>
            <Button size="lg" className="md:w-auto">
              Search Jobs
            </Button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {/* Filters */}
        <div className="mb-8 flex flex-wrap gap-2">
          <span className="text-sm font-medium text-gray-700 self-center mr-2">Department:</span>
          {departments.map(dept => (
            <Button
              key={dept}
              variant={selectedDepartment === dept ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedDepartment(dept)}
            >
              {dept === 'all' ? 'All Departments' : dept}
            </Button>
          ))}
        </div>

        {/* Job Listings */}
        <div className="grid grid-cols-1 gap-6">
          {filteredJobs.length > 0 ? (
            filteredJobs.map(job => (
              <Card key={job.id} className="p-6 hover:shadow-lg transition-shadow cursor-pointer" onClick={() => navigate(`/jobs/${job.id}`)}>
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <h2 className="text-2xl font-semibold">{job.title}</h2>
                      <Badge variant="secondary">{job.type}</Badge>
                    </div>
                    
                    <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
                      <div className="flex items-center gap-1">
                        <Briefcase className="w-4 h-4" />
                        <span>{job.department}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <MapPin className="w-4 h-4" />
                        <span>{job.location}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="w-4 h-4" />
                        <span>Posted {new Date(job.postedDate).toLocaleDateString()}</span>
                      </div>
                    </div>
                    
                    <p className="text-gray-700 line-clamp-2">{job.description}</p>
                    
                    {job.salary && (
                      <p className="text-sm font-medium text-green-600 mt-2">{job.salary}</p>
                    )}
                  </div>
                  
                  <div>
                    <Button 
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/jobs/${job.id}`);
                      }}
                    >
                      View Details
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))
          ) : (
            <Card className="p-12 text-center">
              <p className="text-gray-500 text-lg">No jobs found matching your criteria.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
