import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useJobs } from '../contexts/JobContext';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Plus, 
  Briefcase, 
  Users, 
  TrendingUp, 
  Edit, 
  Trash2,
  Calendar,
  MapPin
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { toast } from 'sonner';

export const ManagerDashboard = () => {
  const { jobs, applications, deleteJob, updateJob } = useJobs();
  const { isManager } = useAuth();
  const navigate = useNavigate();
  const [deleteJobId, setDeleteJobId] = useState<string | null>(null);

  if (!isManager) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <h1 className="text-2xl font-bold mb-4">Access Denied</h1>
          <p className="text-gray-600 mb-6">
            This page is only accessible to managers.
          </p>
          <Button onClick={() => navigate('/')}>
            Go to Home
          </Button>
        </Card>
      </div>
    );
  }

  const activeJobs = jobs.filter(j => j.status === 'active');
  const closedJobs = jobs.filter(j => j.status === 'closed');
  const pendingApplications = applications.filter(a => a.status === 'pending');

  const handleDeleteJob = (id: string) => {
    deleteJob(id);
    setDeleteJobId(null);
    toast.success('Job posting deleted successfully');
  };

  const handleToggleJobStatus = (id: string, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'closed' : 'active';
    updateJob(id, { status: newStatus });
    toast.success(`Job ${newStatus === 'active' ? 'activated' : 'closed'} successfully`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-12">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl md:text-4xl font-bold mb-2">Manager Dashboard</h1>
              <p className="opacity-90">Manage job postings and view applications</p>
            </div>
            <Button 
              size="lg" 
              variant="secondary"
              onClick={() => navigate('/manager/create-job')}
            >
              <Plus className="w-5 h-5 mr-2" />
              Post New Job
            </Button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <Briefcase className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{activeJobs.length}</p>
                <p className="text-sm text-gray-600">Active Jobs</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <Users className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{applications.length}</p>
                <p className="text-sm text-gray-600">Total Applications</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendingApplications.length}</p>
                <p className="text-sm text-gray-600">Pending Review</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Job Listings */}
        <Tabs defaultValue="active" className="w-full">
          <TabsList className="mb-6">
            <TabsTrigger value="active">Active Jobs ({activeJobs.length})</TabsTrigger>
            <TabsTrigger value="closed">Closed Jobs ({closedJobs.length})</TabsTrigger>
            <TabsTrigger value="applications">Applications ({applications.length})</TabsTrigger>
          </TabsList>
          
          <TabsContent value="active" className="space-y-4">
            {activeJobs.length > 0 ? (
              activeJobs.map(job => (
                <JobCard 
                  key={job.id} 
                  job={job} 
                  applications={applications.filter(a => a.jobId === job.id)}
                  onDelete={() => setDeleteJobId(job.id)}
                  onToggleStatus={() => handleToggleJobStatus(job.id, job.status)}
                  navigate={navigate}
                />
              ))
            ) : (
              <Card className="p-12 text-center">
                <Briefcase className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">No Active Jobs</h3>
                <p className="text-gray-600 mb-6">
                  Create your first job posting to start receiving applications.
                </p>
                <Button onClick={() => navigate('/manager/create-job')}>
                  <Plus className="w-4 h-4 mr-2" />
                  Post New Job
                </Button>
              </Card>
            )}
          </TabsContent>
          
          <TabsContent value="closed" className="space-y-4">
            {closedJobs.length > 0 ? (
              closedJobs.map(job => (
                <JobCard 
                  key={job.id} 
                  job={job}
                  applications={applications.filter(a => a.jobId === job.id)}
                  onDelete={() => setDeleteJobId(job.id)}
                  onToggleStatus={() => handleToggleJobStatus(job.id, job.status)}
                  navigate={navigate}
                />
              ))
            ) : (
              <Card className="p-12 text-center">
                <p className="text-gray-500">No closed jobs</p>
              </Card>
            )}
          </TabsContent>
          
          <TabsContent value="applications" className="space-y-4">
            {applications.length > 0 ? (
              applications.map(app => (
                <Card key={app.id} className="p-6">
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-lg font-semibold">{app.candidateName}</h3>
                        <Badge className={getStatusBadgeColor(app.status)}>
                          {app.status}
                        </Badge>
                      </div>
                      <p className="text-gray-600 mb-2">{app.candidateEmail}</p>
                      <p className="text-sm text-gray-500">
                        Applied for: <span className="font-medium">{app.jobTitle}</span>
                      </p>
                      <p className="text-sm text-gray-500">
                        Date: {new Date(app.appliedDate).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm">
                        View Resume
                      </Button>
                      <Button variant="outline" size="sm">
                        Contact
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            ) : (
              <Card className="p-12 text-center">
                <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No applications yet</p>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteJobId !== null} onOpenChange={() => setDeleteJobId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Job Posting</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this job posting? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => deleteJobId && handleDeleteJob(deleteJobId)}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

interface JobCardProps {
  job: any;
  applications: any[];
  onDelete: () => void;
  onToggleStatus: () => void;
  navigate: any;
}

const JobCard = ({ job, applications, onDelete, onToggleStatus, navigate }: JobCardProps) => {
  return (
    <Card className="p-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <h3 className="text-xl font-semibold">{job.title}</h3>
            <Badge variant={job.status === 'active' ? 'default' : 'secondary'}>
              {job.status}
            </Badge>
            <Badge variant="outline">{job.type}</Badge>
          </div>
          
          <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-2">
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
          
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-600">
              <span className="font-medium text-blue-600">{applications.length}</span> applications
            </span>
            {job.salary && (
              <span className="text-green-600 font-medium">{job.salary}</span>
            )}
          </div>
        </div>
        
        <div className="flex flex-wrap gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => navigate(`/jobs/${job.id}`)}
          >
            View
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={onToggleStatus}
          >
            {job.status === 'active' ? 'Close' : 'Activate'}
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={onDelete}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
};

const getStatusBadgeColor = (status: string) => {
  switch (status) {
    case 'pending': return 'bg-yellow-100 text-yellow-800';
    case 'reviewed': return 'bg-blue-100 text-blue-800';
    case 'accepted': return 'bg-green-100 text-green-800';
    case 'rejected': return 'bg-red-100 text-red-800';
    default: return '';
  }
};
