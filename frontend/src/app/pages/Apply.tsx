import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
import { api, JobDetail } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ArrowLeft, Upload, FileText, CheckCircle2, LogIn, DollarSign, MapPin, Tag } from 'lucide-react';
import { toast } from 'sonner';

export const Apply = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const refFromUrl = searchParams.get('ref') ?? '';
  const { user, firebaseUser, loading: authLoading } = useAuth();
  const isLoggedIn = !!user || !!firebaseUser;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [isLoadingJob, setIsLoadingJob] = useState(true);
  const displayName = user?.name ?? firebaseUser?.displayName ?? '';
  const displayEmail = user?.email ?? firebaseUser?.email ?? '';

  const [formData, setFormData] = useState({
    name: displayName,
    email: displayEmail,
    resume: null as File | null,
    salary_expectation: '',
    current_location: '',
    open_to_relocation: false,
    referral_code: refFromUrl,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const setF = (field: string, value: any) => setFormData((p) => ({ ...p, [field]: value }));

  // Pre-fill name/email once auth resolves
  useEffect(() => {
    if (displayName || displayEmail) {
      setFormData((p) => ({
        ...p,
        name: p.name || displayName,
        email: p.email || displayEmail,
      }));
    }
  }, [displayName, displayEmail]);

  useEffect(() => {
    if (!id) return;
    api.jobs.get(id)
      .then(setJob)
      .catch(() => toast.error('Failed to load job details.'))
      .finally(() => setIsLoadingJob(false));
  }, [id]);

  // Auth gate
  if (!authLoading && !isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <LogIn className="w-8 h-8 text-blue-600" />
          </div>
          <h2 className="text-2xl font-bold mb-2">Sign in to Apply</h2>
          <p className="text-gray-600 mb-6">
            You need to be logged in to submit your application.
          </p>
          <div className="space-y-3">
            <Button
              className="w-full"
              onClick={() => navigate(`/login?next=/jobs/${id}/apply${refFromUrl ? `?ref=${refFromUrl}` : ''}`)}
            >
              <LogIn className="w-4 h-4 mr-2" />
              Sign In / Sign Up
            </Button>
            <Button variant="outline" className="w-full" onClick={() => navigate(`/jobs/${id}`)}>
              Back to Job Details
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (isLoadingJob || authLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold mb-4">Job Not Found</h1>
        <Button onClick={() => navigate('/jobs')}>Back to Jobs</Button>
      </div>
    );
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      const file = e.target.files[0];
      if (file.size > 5 * 1024 * 1024) {
        toast.error('File size must be less than 5MB');
        return;
      }
      setF('resume', file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.resume) {
      toast.error('Please fill in all required fields');
      return;
    }
    setIsSubmitting(true);
    try {
      const salary = formData.salary_expectation ? parseFloat(formData.salary_expectation) : undefined;
      await api.jobs.apply(
        id!,
        formData.name,
        formData.email,
        formData.resume,
        formData.referral_code || undefined,
        salary,
        formData.current_location || undefined,
        formData.open_to_relocation,
      );
      setSubmitted(true);
      toast.success('Application submitted!');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to submit application. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
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
            Thank you for applying to <strong>{job.title}</strong>. We'll review your application and be in touch soon.
          </p>
          <Button variant="outline" className="w-full" onClick={() => navigate('/jobs')}>
            Browse More Jobs
          </Button>
        </Card>
      </div>
    );
  }

  const jobLocations = job.locations?.join(', ') || 'Remote';
  const salaryRange = job.budget_min && job.budget_max
    ? `$${job.budget_min.toLocaleString()} – $${job.budget_max.toLocaleString()}`
    : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-8">
        <div className="container mx-auto px-4">
          <Button
            variant="ghost"
            className="text-white hover:bg-white/20 mb-4"
            onClick={() => navigate(`/jobs/${job.job_id}`)}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Job Details
          </Button>
          <h1 className="text-3xl md:text-4xl font-bold mb-2">Apply for {job.title}</h1>
          <p className="opacity-90">{job.team} • {jobLocations}</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto space-y-6">

          {/* Job context card */}
          <Card className="p-4 bg-blue-50 border-blue-100">
            <div className="flex flex-wrap gap-4 text-sm text-blue-800">
              <span className="flex items-center gap-1">
                <MapPin className="w-4 h-4" /> {jobLocations}
              </span>
              {salaryRange && (
                <span className="flex items-center gap-1">
                  <DollarSign className="w-4 h-4" /> {salaryRange}
                </span>
              )}
              <span>Experience: {job.experience_min}–{job.experience_max} yrs</span>
            </div>
          </Card>

          <Card className="p-8">
            <h2 className="text-2xl font-semibold mb-6">Application Form</h2>

            <form onSubmit={handleSubmit} className="space-y-6">

              {/* ── Personal Info ── */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="name">Full Name *</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="Jane Smith"
                    value={formData.name}
                    onChange={(e) => setF('name', e.target.value)}
                    required
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email Address *</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="jane@example.com"
                    value={formData.email}
                    onChange={(e) => setF('email', e.target.value)}
                    required
                    className="mt-1.5"
                  />
                </div>
              </div>

              {/* ── Location & Relocation ── */}
              <div className="space-y-3">
                <div>
                  <Label htmlFor="current_location" className="flex items-center gap-1.5">
                    <MapPin className="w-4 h-4 text-gray-400" />
                    Current Location
                  </Label>
                  <Input
                    id="current_location"
                    type="text"
                    placeholder="e.g. Austin, TX"
                    value={formData.current_location}
                    onChange={(e) => setF('current_location', e.target.value)}
                    className="mt-1.5"
                  />
                </div>

                <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                  <input
                    id="relocation"
                    type="checkbox"
                    checked={formData.open_to_relocation}
                    onChange={(e) => setF('open_to_relocation', e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <Label htmlFor="relocation" className="cursor-pointer font-medium">
                      Open to Relocation
                    </Label>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Check this if you're willing to relocate for this position.
                      {job.locations?.length ? ` Role is based in ${jobLocations}.` : ''}
                    </p>
                  </div>
                </div>
              </div>

              {/* ── Salary Expectation ── */}
              <div>
                <Label htmlFor="salary" className="flex items-center gap-1.5">
                  <DollarSign className="w-4 h-4 text-gray-400" />
                  Salary Expectation (Annual USD)
                </Label>
                <div className="relative mt-1.5">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                  <Input
                    id="salary"
                    type="number"
                    min={0}
                    step={1000}
                    placeholder="120000"
                    value={formData.salary_expectation}
                    onChange={(e) => setF('salary_expectation', e.target.value)}
                    className="pl-7"
                  />
                </div>
                {salaryRange && (
                  <p className="text-xs text-gray-500 mt-1">
                    Job budget: {salaryRange}
                  </p>
                )}
              </div>

              {/* ── Resume ── */}
              <div>
                <Label htmlFor="resume">Resume / CV *</Label>
                <div className="mt-1.5">
                  <label
                    htmlFor="resume"
                    className="flex items-center justify-center w-full px-4 py-8 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors"
                  >
                    <div className="text-center">
                      {formData.resume ? (
                        <>
                          <FileText className="w-12 h-12 text-green-600 mx-auto mb-2" />
                          <p className="text-sm font-medium text-gray-900">{formData.resume.name}</p>
                          <p className="text-xs text-gray-500 mt-1">
                            {(formData.resume.size / 1024).toFixed(1)} KB — click to change
                          </p>
                        </>
                      ) : (
                        <>
                          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                          <p className="text-sm font-medium text-gray-900">
                            Click to upload or drag and drop
                          </p>
                          <p className="text-xs text-gray-500 mt-1">PDF, DOC, DOCX (max 5MB)</p>
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

              {/* ── Referral Code ── */}
              <div>
                <Label htmlFor="referral" className="flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-gray-400" />
                  Referral Code
                  <span className="text-xs font-normal text-gray-400">(optional)</span>
                </Label>
                <Input
                  id="referral"
                  type="text"
                  placeholder="Enter referral code if you have one"
                  value={formData.referral_code}
                  onChange={(e) => setF('referral_code', e.target.value)}
                  className="mt-1.5 font-mono"
                />
                {refFromUrl && (
                  <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Referral code applied from your invite link
                  </p>
                )}
              </div>

              {/* ── Submit ── */}
              <div className="flex gap-3 pt-2">
                <Button type="submit" className="flex-1" size="lg" disabled={isSubmitting}>
                  {isSubmitting ? 'Submitting…' : 'Submit Application'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={() => navigate(`/jobs/${job.job_id}`)}
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
