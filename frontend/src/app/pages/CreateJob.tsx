import { useState } from 'react';
import { useNavigate } from 'react-router';
import { api } from '../services/apiService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { ArrowLeft, Plus, X, Users, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

export const CreateJob = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);

  const [form, setForm] = useState({
    title: '',
    team: '',
    role_description: '',
    headcount: 1,
    budget_min: 0,
    budget_max: 0,
    experience_min: 0,
    experience_max: 0,
    locations: [''],
    total_interview_rounds: 3,
    referrals_enabled: false,
  });

  const set = (field: string, value: any) => setForm((p) => ({ ...p, [field]: value }));

  // Locations list helpers
  const addLocation = () => set('locations', [...form.locations, '']);
  const removeLocation = (i: number) =>
    set('locations', form.locations.filter((_, idx) => idx !== i));
  const updateLocation = (i: number, v: string) => {
    const updated = [...form.locations];
    updated[i] = v;
    set('locations', updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const validLocations = form.locations.map((l) => l.trim()).filter(Boolean);
    if (validLocations.length === 0) {
      toast.error('Add at least one location.');
      return;
    }
    if (form.budget_min >= form.budget_max) {
      toast.error('Budget max must be greater than budget min.');
      return;
    }
    if (form.experience_min > form.experience_max) {
      toast.error('Experience max must be ≥ experience min.');
      return;
    }

    setIsLoading(true);
    try {
      await api.jobs.create({
        title: form.title,
        team: form.team,
        role_description: form.role_description,
        headcount: form.headcount,
        budget_min: form.budget_min,
        budget_max: form.budget_max,
        experience_min: form.experience_min,
        experience_max: form.experience_max,
        locations: validLocations,
        total_interview_rounds: form.total_interview_rounds,
        referrals_enabled: form.referrals_enabled,
      });
      toast.success('Job posted! Agent 1 is now sourcing candidates.');
      navigate('/manager');
    } catch (err: any) {
      toast.error(err.message ?? 'Failed to post job.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-8">
        <div className="container mx-auto px-4">
          <Button
            variant="ghost"
            className="text-white hover:bg-white/20 mb-4"
            onClick={() => navigate('/manager')}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
          <h1 className="text-3xl md:text-4xl font-bold">Post a New Job</h1>
          <p className="opacity-80 mt-1">
            Submitting will automatically trigger Agent 1 to source candidates.
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto">
          <Card className="p-8">
            <form onSubmit={handleSubmit} className="space-y-8">

              {/* ── Basic Info ── */}
              <section>
                <h2 className="text-lg font-semibold mb-4 pb-2 border-b">Basic Information</h2>
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="title">Job Title *</Label>
                      <Input
                        id="title"
                        placeholder="e.g. Senior Software Engineer"
                        value={form.title}
                        onChange={(e) => set('title', e.target.value)}
                        className="mt-1.5"
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="team">Team / Department *</Label>
                      <Input
                        id="team"
                        placeholder="e.g. Platform Engineering"
                        value={form.team}
                        onChange={(e) => set('team', e.target.value)}
                        className="mt-1.5"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="headcount">Headcount *</Label>
                    <Input
                      id="headcount"
                      type="number"
                      min={1}
                      value={form.headcount}
                      onChange={(e) => set('headcount', parseInt(e.target.value) || 1)}
                      className="mt-1.5 w-32"
                      required
                    />
                  </div>

                  <div>
                    <Label htmlFor="desc">Role Description *</Label>
                    <Textarea
                      id="desc"
                      placeholder="Describe the role, responsibilities, and what you're looking for..."
                      value={form.role_description}
                      onChange={(e) => set('role_description', e.target.value)}
                      className="mt-1.5 min-h-36"
                      required
                    />
                  </div>
                </div>
              </section>

              {/* ── Budget ── */}
              <section>
                <h2 className="text-lg font-semibold mb-4 pb-2 border-b">Budget (Annual USD)</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="bmin">Budget Min *</Label>
                    <Input
                      id="bmin"
                      type="number"
                      min={0}
                      placeholder="80000"
                      value={form.budget_min || ''}
                      onChange={(e) => set('budget_min', parseFloat(e.target.value) || 0)}
                      className="mt-1.5"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="bmax">Budget Max *</Label>
                    <Input
                      id="bmax"
                      type="number"
                      min={0}
                      placeholder="150000"
                      value={form.budget_max || ''}
                      onChange={(e) => set('budget_max', parseFloat(e.target.value) || 0)}
                      className="mt-1.5"
                      required
                    />
                  </div>
                </div>
              </section>

              {/* ── Experience ── */}
              <section>
                <h2 className="text-lg font-semibold mb-4 pb-2 border-b">Experience (Years)</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="emin">Minimum *</Label>
                    <Input
                      id="emin"
                      type="number"
                      min={0}
                      value={form.experience_min}
                      onChange={(e) => set('experience_min', parseInt(e.target.value) || 0)}
                      className="mt-1.5"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="emax">Maximum *</Label>
                    <Input
                      id="emax"
                      type="number"
                      min={0}
                      value={form.experience_max}
                      onChange={(e) => set('experience_max', parseInt(e.target.value) || 0)}
                      className="mt-1.5"
                      required
                    />
                  </div>
                </div>
              </section>

              {/* ── Locations ── */}
              <section>
                <div className="flex items-center justify-between mb-4 pb-2 border-b">
                  <h2 className="text-lg font-semibold">Locations *</h2>
                  <Button type="button" variant="outline" size="sm" onClick={addLocation}>
                    <Plus className="w-4 h-4 mr-1" />
                    Add
                  </Button>
                </div>
                <div className="space-y-3">
                  {form.locations.map((loc, i) => (
                    <div key={i} className="flex gap-2">
                      <Input
                        placeholder={`e.g. San Francisco, CA`}
                        value={loc}
                        onChange={(e) => updateLocation(i, e.target.value)}
                      />
                      {form.locations.length > 1 && (
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          onClick={() => removeLocation(i)}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* ── Interview Configuration ── */}
              <section>
                <h2 className="text-lg font-semibold mb-4 pb-2 border-b flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-blue-600" />
                  Interview Configuration
                </h2>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="rounds">Number of Interview Rounds</Label>
                    <div className="flex items-center gap-3 mt-1.5">
                      <Input
                        id="rounds"
                        type="number"
                        min={1}
                        max={10}
                        value={form.total_interview_rounds}
                        onChange={(e) => set('total_interview_rounds', Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                        className="w-24"
                      />
                      <span className="text-sm text-gray-500">rounds (1–10)</span>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <input
                      id="referrals"
                      type="checkbox"
                      checked={form.referrals_enabled}
                      onChange={(e) => set('referrals_enabled', e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <div>
                      <Label htmlFor="referrals" className="cursor-pointer flex items-center gap-1.5">
                        <Users className="w-4 h-4 text-blue-600" />
                        Enable Referrals
                      </Label>
                      <p className="text-xs text-gray-500 mt-0.5">
                        Sourced candidates receive a personal referral link. Portal applicants who
                        apply through that link get a scoring bonus.
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              {/* ── Actions ── */}
              <div className="flex gap-3 pt-2">
                <Button type="submit" className="flex-1" size="lg" disabled={isLoading}>
                  {isLoading ? 'Posting…' : 'Post Job & Start Sourcing'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={() => navigate('/manager')}
                  disabled={isLoading}
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
