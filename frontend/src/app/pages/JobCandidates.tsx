import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api, Candidate, JobDetail, JobReport } from '../services/apiService';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  ArrowLeft, Trophy, GitBranch, BarChart3, MessageSquare,
  Github, Linkedin, MapPin, Star, RefreshCw, AlertTriangle
} from 'lucide-react';
import { toast } from 'sonner';

// ── Stage helpers ──────────────────────────────────────────────────────────────

const STAGE_ORDER = [
  'SOURCED', 'OA_SENT', 'OA_FAILED', 'BEHAVIORAL_COMPLETE',
  'SCORED', 'SHORTLISTED', 'INTERVIEW_SCHEDULED', 'INTERVIEW_DONE',
  'OFFERED', 'HIRED', 'REJECTED',
  'EXPERIENCE_REJECTED', 'LOCATION_REJECTED', 'SALARY_REJECTED', 'OVERQUALIFIED_REJECTED',
];

const STAGE_LABEL: Record<string, string> = {
  SOURCED: 'Sourced',
  OA_SENT: 'OA Sent',
  OA_FAILED: 'OA Failed',
  BEHAVIORAL_COMPLETE: 'Behavioral Done',
  SCORED: 'Scored',
  SHORTLISTED: 'Shortlisted',
  INTERVIEW_SCHEDULED: 'Interview Scheduled',
  INTERVIEW_DONE: 'Interview Done',
  OFFERED: 'Offered',
  HIRED: 'Hired',
  REJECTED: 'Rejected',
  EXPERIENCE_REJECTED: 'Experience Rejected',
  LOCATION_REJECTED: 'Location Rejected',
  SALARY_REJECTED: 'Salary Rejected',
  OVERQUALIFIED_REJECTED: 'Overqualified',
};

const STAGE_COLOR: Record<string, string> = {
  SOURCED: 'bg-blue-100 text-blue-800',
  OA_SENT: 'bg-yellow-100 text-yellow-800',
  OA_FAILED: 'bg-red-100 text-red-800',
  BEHAVIORAL_COMPLETE: 'bg-purple-100 text-purple-800',
  SCORED: 'bg-indigo-100 text-indigo-800',
  SHORTLISTED: 'bg-green-100 text-green-800',
  INTERVIEW_SCHEDULED: 'bg-teal-100 text-teal-800',
  INTERVIEW_DONE: 'bg-cyan-100 text-cyan-800',
  OFFERED: 'bg-emerald-100 text-emerald-800',
  HIRED: 'bg-green-200 text-green-900',
  REJECTED: 'bg-red-100 text-red-800',
  EXPERIENCE_REJECTED: 'bg-orange-100 text-orange-800',
  LOCATION_REJECTED: 'bg-orange-100 text-orange-800',
  SALARY_REJECTED: 'bg-orange-100 text-orange-800',
  OVERQUALIFIED_REJECTED: 'bg-orange-100 text-orange-800',
};

// All backend scores are already on a 0–100 scale
const pct = (v: number | null | undefined) =>
  v != null && v > 0 ? `${Math.round(v)}%` : '—';

const score = (v: number | null | undefined) =>
  v != null && v > 0 ? v.toFixed(1) : '—';

const composite = (v: number | null | undefined) =>
  v != null ? `${v.toFixed(1)} / 100` : '—';

// ── Sub-components ─────────────────────────────────────────────────────────────

const StageBadge = ({ stage }: { stage: string }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STAGE_COLOR[stage] ?? 'bg-gray-100 text-gray-700'}`}>
    {STAGE_LABEL[stage] ?? stage}
  </span>
);

const CandidateCard = ({ c }: { c: Candidate }) => (
  <Card className="p-4">
    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="font-semibold truncate">{c.name}</p>
          <StageBadge stage={c.pipeline_stage} />
          {c.shortlisted && (
            <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full font-medium">
              Shortlisted
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-2">{c.email || '—'}</p>
        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          {c.location && (
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" /> {c.location}
            </span>
          )}
          {c.github_url && (
            <a href={c.github_url} target="_blank" rel="noreferrer"
              className="flex items-center gap-1 text-blue-600 hover:underline">
              <Github className="w-3 h-3" /> GitHub
            </a>
          )}
          {c.linkedin_url && (
            <a href={c.linkedin_url} target="_blank" rel="noreferrer"
              className="flex items-center gap-1 text-blue-600 hover:underline">
              <Linkedin className="w-3 h-3" /> LinkedIn
            </a>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-center text-sm shrink-0">
        <div>
          <p className="font-semibold">{score(c.source_score)}</p>
          <p className="text-xs text-gray-500">Source</p>
        </div>
        <div>
          <p className="font-semibold">{pct(c.oa_score)}</p>
          <p className="text-xs text-gray-500">OA</p>
        </div>
        <div>
          <p className="font-semibold">{pct(c.behavioral_score)}</p>
          <p className="text-xs text-gray-500">Behavioral</p>
        </div>
        <div>
          <p className={`font-bold ${(c.composite_score ?? 0) >= 75 ? 'text-green-600' : (c.composite_score ?? 0) > 0 ? 'text-amber-600' : 'text-gray-400'}`}>
            {composite(c.composite_score)}
          </p>
          <p className="text-xs text-gray-500">Composite</p>
        </div>
      </div>
    </div>
  </Card>
);

// ── Rankings Tab ──────────────────────────────────────────────────────────────

const RankingsTab = ({ candidates }: { candidates: Candidate[] }) => {
  const ranked = [...candidates]
    .filter((c) => c.composite_score != null)
    .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));

  const unscored = candidates.filter((c) => c.composite_score == null);

  if (ranked.length === 0 && unscored.length === 0) {
    return <EmptyState icon={<Trophy />} text="No candidates sourced yet." />;
  }

  return (
    <div className="space-y-4">
      {ranked.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500 font-medium">Ranked candidates ({ranked.length})</p>
          {ranked.map((c, i) => (
            <div key={c.candidate_id} className="flex gap-3 items-start">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 mt-1
                ${i === 0 ? 'bg-amber-400 text-white' : i === 1 ? 'bg-gray-300 text-gray-800' : i === 2 ? 'bg-amber-700 text-white' : 'bg-gray-100 text-gray-600'}`}>
                {i + 1}
              </div>
              <div className="flex-1">
                <CandidateCard c={c} />
              </div>
            </div>
          ))}
        </div>
      )}
      {unscored.length > 0 && (
        <div className="space-y-3 mt-6">
          <p className="text-sm text-gray-400 font-medium">Not yet scored ({unscored.length})</p>
          {unscored.map((c) => <CandidateCard key={c.candidate_id} c={c} />)}
        </div>
      )}
    </div>
  );
};

// ── Pipeline Tab ──────────────────────────────────────────────────────────────

const PipelineTab = ({ candidates }: { candidates: Candidate[] }) => {
  const grouped = STAGE_ORDER.reduce<Record<string, Candidate[]>>((acc, stage) => {
    const group = candidates.filter((c) => c.pipeline_stage === stage);
    if (group.length) acc[stage] = group;
    return acc;
  }, {});

  if (Object.keys(grouped).length === 0) {
    return <EmptyState icon={<GitBranch />} text="No candidates in the pipeline yet." />;
  }

  return (
    <div className="space-y-8">
      {Object.entries(grouped).map(([stage, list]) => (
        <div key={stage}>
          <div className="flex items-center gap-2 mb-3">
            <StageBadge stage={stage} />
            <span className="text-sm text-gray-500">{list.length} candidate{list.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="space-y-3 pl-2 border-l-2 border-gray-100">
            {list.map((c) => <CandidateCard key={c.candidate_id} c={c} />)}
          </div>
        </div>
      ))}
    </div>
  );
};

// ── Score slider helper ───────────────────────────────────────────────────────

const ScoreInput = ({
  label, value, onChange, hint,
}: { label: string; value: number; onChange: (v: number) => void; hint?: string }) => (
  <div>
    <div className="flex items-center justify-between mb-1">
      <Label className="text-sm">{label}</Label>
      <span className={`text-sm font-bold ${value >= 8 ? 'text-green-600' : value >= 5 ? 'text-yellow-600' : 'text-red-600'}`}>
        {value}/10
      </span>
    </div>
    <input
      type="range" min={1} max={10} step={1}
      value={value}
      onChange={(e) => onChange(parseInt(e.target.value))}
      className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-gray-200 accent-blue-600"
    />
    {hint && <p className="text-xs text-gray-400 mt-0.5">{hint}</p>}
  </div>
);

// ── Interview Feedback Tab ────────────────────────────────────────────────────

const FeedbackTab = ({ jobId, candidates }: { jobId: string; candidates: Candidate[] }) => {
  const eligible = candidates.filter((c) =>
    ['SHORTLISTED', 'INTERVIEW_SCHEDULED', 'INTERVIEW_DONE'].includes(c.pipeline_stage)
  );

  const [selectedId, setSelectedId] = useState('');
  const [form, setForm] = useState({
    round_number: 1,
    total_rounds: 1,
    result: '' as 'SELECTED' | 'REJECTED' | '',
    feedback: '',
    interviewer_name: '',
    technical_score: 5,
    communication_score: 5,
    problem_solving_score: 5,
    cultural_fit_score: 5,
    recommendation: '' as 'strong_yes' | 'yes' | 'neutral' | 'no' | 'strong_no' | '',
  });
  const [isLoading, setIsLoading] = useState(false);

  const selected = candidates.find((c) => c.candidate_id === selectedId);
  const setF = (field: string, value: any) => setForm((p) => ({ ...p, [field]: value }));

  // Auto-populate round info when candidate changes
  const prevSelectedId = useRef('');
  useEffect(() => {
    if (!selectedId || selectedId === prevSelectedId.current) return;
    prevSelectedId.current = selectedId;
    const c = candidates.find((x) => x.candidate_id === selectedId);
    if (!c) return;
    const nextRound = Math.max(1, (c.current_round ?? 0) + 1);
    const totalRounds = c.total_rounds > 0 ? c.total_rounds : 1;
    setForm((p) => ({
      ...p,
      round_number: Math.min(nextRound, totalRounds),
      total_rounds: totalRounds,
    }));
  }, [selectedId, candidates]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId || !form.result) return;
    setIsLoading(true);
    try {
      await api.candidates.submitInterviewFeedback(jobId, selectedId, {
        round_number: form.round_number,
        total_rounds: form.total_rounds,
        result: form.result as 'SELECTED' | 'REJECTED',
        feedback: form.feedback,
        interviewer_name: form.interviewer_name || undefined,
        technical_score: form.technical_score,
        communication_score: form.communication_score,
        problem_solving_score: form.problem_solving_score,
        cultural_fit_score: form.cultural_fit_score,
        recommendation: form.recommendation || undefined,
      });
      toast.success(`Feedback submitted for ${selected?.name}.`);
      setForm({
        round_number: 1, total_rounds: 1, result: '', feedback: '', interviewer_name: '',
        technical_score: 5, communication_score: 5, problem_solving_score: 5,
        cultural_fit_score: 5, recommendation: '',
      });
      prevSelectedId.current = '';
      setSelectedId('');
    } catch (err: any) {
      toast.error(err.message ?? 'Failed to submit feedback.');
    } finally {
      setIsLoading(false);
    }
  };

  if (eligible.length === 0) {
    return (
      <EmptyState
        icon={<MessageSquare />}
        text="No shortlisted candidates yet. Candidates must reach SHORTLISTED stage."
      />
    );
  }

  return (
    <Card className="p-6 max-w-2xl">
      <h3 className="font-semibold mb-4">Submit Interview Feedback</h3>
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Candidate + round */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label>Candidate *</Label>
            <Select value={selectedId} onValueChange={setSelectedId}>
              <SelectTrigger className="mt-1.5">
                <SelectValue placeholder="Select a candidate" />
              </SelectTrigger>
              <SelectContent>
                {eligible.map((c) => (
                  <SelectItem key={c.candidate_id} value={c.candidate_id}>
                    {c.name} — {STAGE_LABEL[c.pipeline_stage]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Interviewer Name</Label>
            <Input
              placeholder="e.g. Jane Smith"
              value={form.interviewer_name}
              onChange={(e) => setF('interviewer_name', e.target.value)}
              className="mt-1.5"
            />
          </div>
        </div>

        {selected && (
          <div className="text-xs text-gray-500 bg-gray-50 rounded p-2">
            Current round: {selected.current_round} / {selected.total_rounds || '?'}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Round Number *</Label>
            <Input
              type="number" min={1}
              value={form.round_number}
              onChange={(e) => setF('round_number', parseInt(e.target.value) || 1)}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label>Total Rounds *</Label>
            <Input
              type="number" min={1}
              value={form.total_rounds}
              onChange={(e) => setF('total_rounds', parseInt(e.target.value) || 1)}
              className="mt-1.5"
            />
          </div>
        </div>

        {/* Structured scores */}
        <div className="border rounded-lg p-4 space-y-4 bg-gray-50">
          <p className="text-sm font-medium text-gray-700">Structured Scores (used in composite ranking)</p>
          <ScoreInput label="Technical Skills" value={form.technical_score}
            onChange={(v) => setF('technical_score', v)}
            hint="Coding ability, domain knowledge, system design" />
          <ScoreInput label="Communication" value={form.communication_score}
            onChange={(v) => setF('communication_score', v)}
            hint="Clarity, articulation, listening" />
          <ScoreInput label="Problem Solving" value={form.problem_solving_score}
            onChange={(v) => setF('problem_solving_score', v)}
            hint="Logical thinking, approach to ambiguity" />
          <ScoreInput label="Cultural Fit" value={form.cultural_fit_score}
            onChange={(v) => setF('cultural_fit_score', v)}
            hint="Team alignment, values, collaboration" />

          <div>
            <Label>Recommendation</Label>
            <Select value={form.recommendation} onValueChange={(v) => setF('recommendation', v)}>
              <SelectTrigger className="mt-1.5">
                <SelectValue placeholder="Overall recommendation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="strong_yes">Strong Yes — definitely hire</SelectItem>
                <SelectItem value="yes">Yes — good candidate</SelectItem>
                <SelectItem value="neutral">Neutral — could go either way</SelectItem>
                <SelectItem value="no">No — not a fit</SelectItem>
                <SelectItem value="strong_no">Strong No — clear reject</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <Label>Overall Result *</Label>
          <Select value={form.result} onValueChange={(v) => setF('result', v as any)}>
            <SelectTrigger className="mt-1.5">
              <SelectValue placeholder="Select result" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="SELECTED">Selected — advance to next round / offer</SelectItem>
              <SelectItem value="REJECTED">Rejected</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label>Notes / Detailed Feedback *</Label>
          <Textarea
            placeholder="Interview notes, specific strengths, areas of concern..."
            value={form.feedback}
            onChange={(e) => setF('feedback', e.target.value)}
            className="mt-1.5 min-h-28"
            required
          />
        </div>

        <Button
          type="submit"
          className="w-full"
          disabled={isLoading || !selectedId || !form.result || !form.feedback}
        >
          {isLoading ? 'Submitting…' : 'Submit Feedback & Update Score'}
        </Button>
      </form>
    </Card>
  );
};

// ── Report Tab ────────────────────────────────────────────────────────────────

const ReportTab = ({ jobId }: { jobId: string }) => {
  const [report, setReport] = useState<JobReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const fetchReport = async () => {
    setIsLoading(true);
    try {
      const data = await api.jobs.report(jobId);
      setReport(data);
      setFetched(true);
    } catch (err: any) {
      toast.error(err.message ?? 'Failed to fetch report.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!fetched) {
    return (
      <div className="text-center py-12">
        <BarChart3 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-500 mb-4">
          Generate a full audit report with salary analysis and top candidate recommendations.
        </p>
        <Button onClick={fetchReport} disabled={isLoading}>
          {isLoading ? 'Generating…' : 'Generate Report'}
        </Button>
      </div>
    );
  }

  if (!report) return null;

  const sr = report.salary_report;

  return (
    <div className="space-y-6">
      {/* Salary Report */}
      {sr ? (
        <Card className="p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-600" /> Market Salary Analysis
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {[['P25', sr.p25], ['P50 (Median)', sr.p50], ['P75', sr.p75], ['P90', sr.p90]].map(([label, val]) => (
              <div key={label as string} className="text-center bg-gray-50 rounded p-3">
                <p className="text-lg font-bold">${Number(val).toLocaleString()}</p>
                <p className="text-xs text-gray-500">{label}</p>
              </div>
            ))}
          </div>
          <div className="text-sm text-gray-600 space-y-1">
            <p>Budget: <span className="font-medium">${sr.budget_min.toLocaleString()} – ${sr.budget_max.toLocaleString()}</span></p>
            {sr.budget_warning && (
              <p className="flex items-center gap-1 text-amber-600">
                <AlertTriangle className="w-4 h-4" /> Budget may be below market median
              </p>
            )}
            {sr.analysis_summary && <p className="mt-2 text-gray-700">{sr.analysis_summary}</p>}
          </div>
        </Card>
      ) : (
        <Card className="p-4 text-sm text-gray-500">Salary report not yet generated.</Card>
      )}

      {/* Audit */}
      {report.audit && (
        <Card className="p-6">
          <h3 className="font-semibold mb-3">Audit Summary</h3>
          <p className="text-sm text-gray-700 mb-4">{report.audit.summary}</p>
          {report.audit.flags?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-red-600 uppercase mb-1">Flags</p>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                {report.audit.flags.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
          {report.audit.recommendations?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-600 uppercase mb-1">Recommendations</p>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                {report.audit.recommendations.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
        </Card>
      )}

      {/* Top Candidates */}
      {report.top_candidates?.length > 0 && (
        <div>
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Star className="w-5 h-5 text-amber-500" /> Top Shortlisted Candidates
          </h3>
          <div className="space-y-3">
            {report.top_candidates.map((c) => <CandidateCard key={c.candidate_id} c={c} />)}
          </div>
        </div>
      )}

      <Button variant="outline" size="sm" onClick={fetchReport} disabled={isLoading}>
        <RefreshCw className="w-4 h-4 mr-2" />
        Refresh Report
      </Button>
    </div>
  );
};

// ── Empty state ───────────────────────────────────────────────────────────────

const EmptyState = ({ icon, text }: { icon: React.ReactNode; text: string }) => (
  <div className="text-center py-16 text-gray-400">
    <div className="w-12 h-12 mx-auto mb-3 opacity-30">{icon}</div>
    <p>{text}</p>
  </div>
);

// ── Main page ─────────────────────────────────────────────────────────────────

export const JobCandidates = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const [job, setJob] = useState<JobDetail | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const [jobData, candData] = await Promise.all([
        api.jobs.get(jobId),
        api.candidates.list(jobId),
      ]);
      setJob(jobData);
      setCandidates(candData.candidates);
    } catch (err: any) {
      toast.error(err.message ?? 'Failed to load data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, [jobId]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Job not found.</p>
      </div>
    );
  }

  const shortlisted = candidates.filter((c) => c.shortlisted).length;
  const inInterview = candidates.filter((c) =>
    ['INTERVIEW_SCHEDULED', 'INTERVIEW_DONE'].includes(c.pipeline_stage)
  ).length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
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
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold">{job.title}</h1>
              <p className="opacity-80 mt-1">{job.team} · {job.locations?.join(', ')}</p>
            </div>
            <div className="flex gap-4 text-sm">
              <div className="text-center">
                <p className="text-2xl font-bold">{candidates.length}</p>
                <p className="opacity-80">Total</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold">{shortlisted}</p>
                <p className="opacity-80">Shortlisted</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold">{inInterview}</p>
                <p className="opacity-80">In Interview</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-end mb-4">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </Button>
        </div>

        <Tabs defaultValue="rankings">
          <TabsList className="mb-6 flex-wrap h-auto gap-1">
            <TabsTrigger value="rankings" className="flex items-center gap-1">
              <Trophy className="w-4 h-4" /> Rankings
            </TabsTrigger>
            <TabsTrigger value="pipeline" className="flex items-center gap-1">
              <GitBranch className="w-4 h-4" /> Pipeline Status
            </TabsTrigger>
            <TabsTrigger value="feedback" className="flex items-center gap-1">
              <MessageSquare className="w-4 h-4" /> Interview Feedback
            </TabsTrigger>
            <TabsTrigger value="report" className="flex items-center gap-1">
              <BarChart3 className="w-4 h-4" /> Report
            </TabsTrigger>
          </TabsList>

          <TabsContent value="rankings">
            <RankingsTab candidates={candidates} />
          </TabsContent>

          <TabsContent value="pipeline">
            <PipelineTab candidates={candidates} />
          </TabsContent>

          <TabsContent value="feedback">
            <FeedbackTab jobId={jobId!} candidates={candidates} />
          </TabsContent>

          <TabsContent value="report">
            <ReportTab jobId={jobId!} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};
