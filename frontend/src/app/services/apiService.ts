import { auth } from './firebase';

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

/** Like request() but attaches the Firebase ID token — use for manager endpoints. */
async function authRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await auth.currentUser?.getIdToken();
  if (!token) throw new Error('Not authenticated. Please sign in.');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    ...(options?.headers as Record<string, string> | undefined),
  };
  return request<T>(path, { ...options, headers });
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface OrgSummary {
  org_id: string;
  name: string;
  website?: string;
  description?: string;
  created_at?: string;
}

export interface JobSummary {
  job_id: string;
  title: string;
  status: string;
  headcount: number;
  candidate_count: number;
  created_at: string;
  org_id?: string;
  org_name?: string;
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
  outreach_sent: boolean;
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

export interface MyApplication {
  candidate: Candidate;
  job: JobSummary;
}

export const api = {
  orgs: {
    list: () => request<{ orgs: OrgSummary[] }>('/api/orgs'),
    get: (orgId: string) => request<OrgSummary>(`/api/orgs/${orgId}`),
    create: (payload: { name: string; website?: string; description?: string }) =>
      authRequest<{ org_id: string; name: string }>('/api/orgs', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  },
  jobs: {
    list: (orgId?: string) =>
      request<JobSummary[]>(orgId ? `/api/jobs?org_id=${encodeURIComponent(orgId)}` : '/api/jobs'),
    myApplications: () =>
      authRequest<{ applications: MyApplication[] }>('/api/jobs/my-applications'),
    get: (jobId: string) => request<JobDetail>(`/api/jobs/${jobId}`),
    create: (payload: CreateJobPayload) =>
      authRequest<JobSummary>('/api/jobs', { method: 'POST', body: JSON.stringify(payload) }),
    report: (jobId: string) => authRequest<JobReport>(`/api/jobs/${jobId}/report`),
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
      authRequest<{ job_id: string; candidates: Candidate[] }>(`/api/jobs/${jobId}/candidates`),
    submitInterviewFeedback: (
      jobId: string,
      candidateId: string,
      payload: InterviewFeedbackPayload
    ) =>
      authRequest(`/api/jobs/${jobId}/candidates/${candidateId}/interview-feedback`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    sendOutreachInvite: (jobId: string, candidateId: string) =>
      authRequest<{ sent: boolean; candidate_id: string }>(
        `/api/jobs/${jobId}/candidates/${candidateId}/send-invite`,
        { method: 'POST' },
      ),
    startScreening: (jobId: string, candidateId: string) =>
      authRequest(`/api/jobs/${jobId}/candidates/${candidateId}/start-screening`, { method: 'POST' }),
    retryScreening: (jobId: string, candidateId: string) =>
      authRequest(`/api/jobs/${jobId}/candidates/${candidateId}/retry-screening`, { method: 'POST' }),
  },
};
