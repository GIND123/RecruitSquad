import { useParams, useNavigate } from 'react-router';
import { useJobs } from '../contexts/JobContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { MapPin, Briefcase, Calendar, DollarSign, ArrowLeft, CheckCircle2 } from 'lucide-react';

export const JobDetails = () => {
  const { id } = useParams<{ id: string }>();
  const { jobs } = useJobs();
  const navigate = useNavigate();

  const job = jobs.find(j => j.id === id);

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold mb-4">Job Not Found</h1>
        <Button onClick={() => navigate('/jobs')}>Back to Jobs</Button>
      </div>
    );
  }

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
          
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <h1 className="text-3xl md:text-4xl font-bold">{job.title}</h1>
            <Badge variant="secondary" className="bg-white/20 text-white">
              {job.type}
            </Badge>
          </div>
          
          <div className="flex flex-wrap gap-6 text-sm opacity-90">
            <div className="flex items-center gap-2">
              <Briefcase className="w-4 h-4" />
              <span>{job.department}</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4" />
              <span>{job.location}</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <span>Posted {new Date(job.postedDate).toLocaleDateString()}</span>
            </div>
            {job.salary && (
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                <span>{job.salary}</span>
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
              <p className="text-gray-700 leading-relaxed">{job.description}</p>
            </Card>

            <Card className="p-6">
              <h2 className="text-2xl font-semibold mb-4">Responsibilities</h2>
              <ul className="space-y-3">
                {job.responsibilities.map((resp, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{resp}</span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="p-6">
              <h2 className="text-2xl font-semibold mb-4">Qualifications</h2>
              <ul className="space-y-3">
                {job.requirements.map((req, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{req}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <Card className="p-6 sticky top-24">
              <h3 className="text-xl font-semibold mb-4">Ready to Apply?</h3>
              <p className="text-gray-600 mb-6 text-sm">
                Join our team and make an impact on billions of users worldwide.
              </p>
              
              <Button 
                className="w-full mb-3" 
                size="lg"
                onClick={() => navigate(`/jobs/${job.id}/apply`)}
              >
                Apply Now
              </Button>
              
              <Separator className="my-4" />
              
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-gray-500 mb-1">Department</p>
                  <p className="font-medium">{job.department}</p>
                </div>
                <div>
                  <p className="text-gray-500 mb-1">Location</p>
                  <p className="font-medium">{job.location}</p>
                </div>
                <div>
                  <p className="text-gray-500 mb-1">Employment Type</p>
                  <p className="font-medium">{job.type}</p>
                </div>
                {job.salary && (
                  <div>
                    <p className="text-gray-500 mb-1">Salary Range</p>
                    <p className="font-medium text-green-600">{job.salary}</p>
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
