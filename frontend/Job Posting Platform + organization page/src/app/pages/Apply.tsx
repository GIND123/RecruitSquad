import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useJobs } from '../contexts/JobContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ArrowLeft, Upload, FileText, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

export const Apply = () => {
  const { id } = useParams<{ id: string }>();
  const { jobs, applyToJob } = useJobs();
  const navigate = useNavigate();
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    resume: null as File | null
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const job = jobs.find(j => j.id === id);

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold mb-4">Job Not Found</h1>
        <Button onClick={() => navigate('/jobs')}>Back to Jobs</Button>
      </div>
    );
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 5 * 1024 * 1024) {
        toast.error('File size must be less than 5MB');
        return;
      }
      setFormData({ ...formData, resume: file });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name || !formData.email || !formData.resume) {
      toast.error('Please fill in all fields');
      return;
    }

    setIsSubmitting(true);

    // Simulate file upload delay
    await new Promise(resolve => setTimeout(resolve, 1500));

    // Convert file to base64 for demo storage
    const reader = new FileReader();
    reader.onloadend = () => {
      applyToJob({
        jobId: job.id,
        jobTitle: job.title,
        candidateName: formData.name,
        candidateEmail: formData.email,
        resumeFile: reader.result as string,
        resumeName: formData.resume!.name
      });

      setIsSubmitting(false);
      setSubmitted(true);
      toast.success('Application submitted successfully!');
    };
    reader.readAsDataURL(formData.resume);
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Application Submitted!</h1>
          <p className="text-gray-600 mb-6">
            Thank you for applying to {job.title}. We'll review your application and get back to you soon.
          </p>
          <div className="space-y-3">
            <Button className="w-full" onClick={() => navigate('/profile')}>
              View My Applications
            </Button>
            <Button variant="outline" className="w-full" onClick={() => navigate('/jobs')}>
              Browse More Jobs
            </Button>
          </div>
        </Card>
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
            onClick={() => navigate(`/jobs/${job.id}`)}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Job Details
          </Button>
          
          <h1 className="text-3xl md:text-4xl font-bold mb-2">Apply for {job.title}</h1>
          <p className="opacity-90">{job.department} • {job.location}</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto">
          <Card className="p-8">
            <h2 className="text-2xl font-semibold mb-6">Application Form</h2>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <Label htmlFor="name">Full Name *</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="John Doe"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  className="mt-1.5"
                />
              </div>

              <div>
                <Label htmlFor="email">Email Address *</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="john.doe@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                  className="mt-1.5"
                />
              </div>

              <div>
                <Label htmlFor="resume">Resume/CV *</Label>
                <div className="mt-1.5">
                  <label 
                    htmlFor="resume" 
                    className="flex items-center justify-center w-full px-4 py-8 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors"
                  >
                    <div className="text-center">
                      {formData.resume ? (
                        <>
                          <FileText className="w-12 h-12 text-green-600 mx-auto mb-2" />
                          <p className="text-sm font-medium text-gray-900">
                            {formData.resume.name}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {(formData.resume.size / 1024).toFixed(1)} KB
                          </p>
                        </>
                      ) : (
                        <>
                          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                          <p className="text-sm font-medium text-gray-900">
                            Click to upload or drag and drop
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            PDF, DOC, DOCX (max 5MB)
                          </p>
                        </>
                      )}
                    </div>
                    <input
                      id="resume"
                      type="file"
                      accept=".pdf,.doc,.docx"
                      onChange={handleFileChange}
                      className="hidden"
                      required
                    />
                  </label>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-900">
                  <strong>Note:</strong> By submitting this application, you agree to our privacy policy and terms of service. We will review your application and contact you if there's a match.
                </p>
              </div>

              <div className="flex gap-3">
                <Button 
                  type="submit" 
                  className="flex-1" 
                  size="lg"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Submitting...' : 'Submit Application'}
                </Button>
                <Button 
                  type="button" 
                  variant="outline" 
                  size="lg"
                  onClick={() => navigate(`/jobs/${job.id}`)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
};
