import { useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { useJobs } from '../contexts/JobContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { User, Mail, Briefcase, Calendar, FileText, ArrowRight } from 'lucide-react';

export const Profile = () => {
  const { user } = useAuth();
  const { getUserApplications } = useJobs();
  const navigate = useNavigate();

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <h1 className="text-2xl font-bold mb-4">Login Required</h1>
          <p className="text-gray-600 mb-6">
            Please login to view your profile and applications.
          </p>
          <Button onClick={() => navigate('/login')}>
            Go to Login
          </Button>
        </Card>
      </div>
    );
  }

  const applications = getUserApplications(user.email);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'reviewed': return 'bg-blue-100 text-blue-800';
      case 'accepted': return 'bg-green-100 text-green-800';
      case 'rejected': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

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
                  <span className="text-gray-700">{applications.length} Applications</span>
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
            
            {applications.length > 0 ? (
              <div className="space-y-4">
                {applications.map(app => (
                  <Card key={app.id} className="p-6 hover:shadow-lg transition-shadow">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <h3 className="text-xl font-semibold">{app.jobTitle}</h3>
                          <Badge className={getStatusColor(app.status)}>
                            {app.status.charAt(0).toUpperCase() + app.status.slice(1)}
                          </Badge>
                        </div>
                        
                        <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
                          <div className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            <span>Applied {new Date(app.appliedDate).toLocaleDateString()}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <FileText className="w-4 h-4" />
                            <span>{app.resumeName}</span>
                          </div>
                        </div>

                        {app.status === 'pending' && (
                          <p className="text-sm text-gray-500">
                            Your application is under review. We'll notify you of any updates.
                          </p>
                        )}
                        {app.status === 'reviewed' && (
                          <p className="text-sm text-blue-600">
                            Your application has been reviewed. We'll be in touch soon!
                          </p>
                        )}
                        {app.status === 'accepted' && (
                          <p className="text-sm text-green-600">
                            Congratulations! We'd like to move forward with your application.
                          </p>
                        )}
                        {app.status === 'rejected' && (
                          <p className="text-sm text-gray-500">
                            Unfortunately, we've decided to move forward with other candidates.
                          </p>
                        )}
                      </div>

                      <div>
                        <Button 
                          variant="outline"
                          onClick={() => navigate(`/jobs/${app.jobId}`)}
                        >
                          View Job
                        </Button>
                      </div>
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
                <Button onClick={() => navigate('/jobs')}>
                  Explore Jobs
                </Button>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
