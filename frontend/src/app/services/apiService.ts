const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Request failed');
  }
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface JobSummary {
  job_id: string;
  title: string;
  status: string;
  headcount: number;
  candidate_count: number;
  created_at: string;
}

export interface JobDetail extends JobSummary {
  role_description: string;
  budget_min: number;
  budget_max: number;
  locations: string[];
  experience_min: number;
  experience_max: number;
  team: string;
  salary_report?: SalaryReport;
  audit?: AuditResult;
}

export interface Candidate {
  candidate_id: string;
  job_id: string;
  name: string;
  email: string;
  github_url: string;
  linkedin_url: string | null;
  location: string;
  source: string;
  pipeline_stage: string;
  source_score: number;
  composite_score: number | null;
  rank: number | null;
  shortlisted: boolean;
  oa_score: number;
  oa_passed: boolean;
  behavioral_score: number;
  behavioral_complete: boolean;
  interview_status: string;
  current_round: number;
  total_rounds: number;
  overall_interview_result: string;
  interview_rounds: Record<string, InterviewRound>;
  created_at: string;
  updated_at: string;
}

export interface InterviewRound {
  round_number: number;
  result: string;
  feedback: string;
  interviewer_name: string | null;
  completed_at: string;
}

export interface SalaryReport {
  job_id: string;
  location: string;
  role_title: string;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  budget_min: number;
  budget_max: number;
  budget_warning: boolean;
  analysis_summary: string | null;
  generated_at: string;
}

export interface AuditResult {
  summary: string;
  flags: string[];
  recommendations: string[];
  generated_at: string;
}

export interface JobReport {
  job_id: string;
  salary_report: SalaryReport | null;
  top_candidates: Candidate[];
  audit: AuditResult;
}

export interface CreateJobPayload {
  title: string;
  role_description: string;
  headcount: number;
  budget_min: number;
  budget_max: number;
  locations: string[];
  experience_min: number;
  experience_max: number;
  team: string;
  total_interview_rounds?: number;
  referrals_enabled?: boolean;
}

export interface InterviewFeedbackPayload {
  round_number: number;
  result: 'SELECTED' | 'REJECTED';
  feedback: string;
  interviewer_name?: string;
  total_rounds: number;
  technical_score?: number;
  communication_score?: number;
  problem_solving_score?: number;
  cultural_fit_score?: number;
  recommendation?: 'strong_yes' | 'yes' | 'neutral' | 'no' | 'strong_no';
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  jobs: {
    list: () => request<JobSummary[]>('/api/jobs'),
    get: (jobId: string) => request<JobDetail>(`/api/jobs/${jobId}`),
    create: (payload: CreateJobPayload) =>
      request<JobSummary>('/api/jobs', { method: 'POST', body: JSON.stringify(payload) }),
    report: (jobId: string) => request<JobReport>(`/api/jobs/${jobId}/report`),
    apply: async (
      jobId: string,
      name: string,
      email: string,
      resume: File,
      referralToken?: string,
      salaryExpectation?: number,
      currentLocation?: string,
      openToRelocation?: boolean,
    ) => {
      const form = new FormData();
      form.append('name', name);
      form.append('email', email);
      form.append('resume', resume);
      if (referralToken) form.append('referral_token', referralToken);
      if (salaryExpectation != null) form.append('salary_expectation', String(salaryExpectation));
      if (currentLocation) form.append('current_location', currentLocation);
      if (openToRelocation != null) form.append('open_to_relocation', String(openToRelocation));
      const res = await fetch(`${BASE}/api/jobs/${jobId}/apply`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? 'Application failed');
      }
      return res.json() as Promise<{ candidate_id: string; resume_url: string; message: string }>;
    },
  },
  candidates: {
    list: (jobId: string) =>
      request<{ job_id: string; candidates: Candidate[] }>(`/api/jobs/${jobId}/candidates`),
    submitInterviewFeedback: (
      jobId: string,
      candidateId: string,
      payload: InterviewFeedbackPayload
    ) =>
      request(`/api/jobs/${jobId}/candidates/${candidateId}/interview-feedback`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    startScreening: (jobId: string, candidateId: string) =>
      request(`/api/jobs/${jobId}/candidates/${candidateId}/start-screening`, { method: 'POST' }),
  },
};
