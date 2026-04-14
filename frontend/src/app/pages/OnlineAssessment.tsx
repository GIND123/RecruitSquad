import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { CheckCircle2, Clock, Code, List, MessageSquare, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface OAQuestion {
  question_id: string;
  question_text: string;
  type: 'MCQ' | 'CODING' | 'TEXT';
  options: string[] | null;
  time_limit_minutes: number | null;
}

interface OAContext {
  oa_token: string;
  candidate_name: string;
  job_title: string;
  oa_questions: OAQuestion[];
  already_submitted: boolean;
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  MCQ:    <List className="w-4 h-4" />,
  CODING: <Code className="w-4 h-4" />,
  TEXT:   <MessageSquare className="w-4 h-4" />,
};

const TYPE_COLOR: Record<string, string> = {
  MCQ:    'bg-blue-100 text-blue-800',
  CODING: 'bg-purple-100 text-purple-800',
  TEXT:   'bg-green-100 text-green-800',
};

export const OnlineAssessment = () => {
  const { token } = useParams<{ token: string }>();

  const [ctx, setCtx] = useState<OAContext | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${BASE}/api/jobs/oa/${token}`)
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail ?? 'Failed to load assessment');
        }
        return res.json() as Promise<OAContext>;
      })
      .then((data) => {
        setCtx(data);
        if (data.already_submitted) setSubmitted(true);
      })
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [token]);

  const setAnswer = (questionId: string, value: string) =>
    setAnswers((p) => ({ ...p, [questionId]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ctx) return;

    const unanswered = ctx.oa_questions.filter((q) => !answers[q.question_id]?.trim());
    if (unanswered.length > 0) {
      toast.error(`Please answer all ${unanswered.length} remaining question${unanswered.length > 1 ? 's' : ''}`);
      return;
    }

    setIsSubmitting(true);
    try {
      const responses = ctx.oa_questions.map((q) => ({
        question_id: q.question_id,
        answer: answers[q.question_id] ?? '',
      }));

      const res = await fetch(`${BASE}/api/jobs/oa/${token}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ responses }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Submission failed');
      }

      setSubmitted(true);
      toast.success('Assessment submitted!');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Submission failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Link Not Found</h2>
          <p className="text-gray-600">{error}</p>
        </Card>
      </div>
    );
  }

  // ── Already submitted ────────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Assessment Submitted!</h1>
          <p className="text-gray-600">
            Thank you{ctx?.candidate_name ? `, ${ctx.candidate_name}` : ''}. Your Online Assessment
            for <strong>{ctx?.job_title}</strong> has been received. Our team will review your
            answers and be in touch shortly.
          </p>
        </Card>
      </div>
    );
  }

  if (!ctx) return null;

  const answered = ctx.oa_questions.filter((q) => answers[q.question_id]?.trim()).length;
  const total    = ctx.oa_questions.length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-8">
        <div className="container mx-auto px-4 max-w-3xl">
          <p className="text-sm opacity-75 mb-1">Online Assessment</p>
          <h1 className="text-2xl md:text-3xl font-bold mb-1">{ctx.job_title}</h1>
          {ctx.candidate_name && (
            <p className="opacity-80">Hi {ctx.candidate_name} — complete all questions below</p>
          )}
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 max-w-3xl">
        {/* Progress bar */}
        <Card className="p-4 mb-6">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-600">Progress</span>
            <span className="font-medium">{answered} / {total} answered</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: total > 0 ? `${(answered / total) * 100}%` : '0%' }}
            />
          </div>
        </Card>

        {/* Instructions */}
        <Card className="p-4 mb-6 bg-amber-50 border-amber-200">
          <div className="flex gap-2 text-sm text-amber-800">
            <Clock className="w-4 h-4 shrink-0 mt-0.5" />
            <p>
              Answer all questions thoughtfully. MCQ questions require selecting one option;
              coding and text questions accept written answers. Submit when complete — you cannot
              change your answers after submission.
            </p>
          </div>
        </Card>

        <form onSubmit={handleSubmit} className="space-y-6">
          {ctx.oa_questions.map((q, idx) => (
            <Card key={q.question_id} className="p-6">
              {/* Question header */}
              <div className="flex items-start gap-3 mb-4">
                <span className="text-lg font-bold text-gray-400 shrink-0 mt-0.5 w-6 text-right">
                  {idx + 1}.
                </span>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <Badge className={`${TYPE_COLOR[q.type]} flex items-center gap-1`}>
                      {TYPE_ICON[q.type]}
                      {q.type}
                    </Badge>
                    {q.time_limit_minutes && (
                      <span className="text-xs text-gray-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {q.time_limit_minutes} min
                      </span>
                    )}
                  </div>
                  <p className="text-gray-900 font-medium whitespace-pre-wrap leading-relaxed">
                    {q.question_text}
                  </p>
                </div>
              </div>

              {/* MCQ options */}
              {q.type === 'MCQ' && q.options && q.options.length > 0 ? (
                <div className="space-y-2 ml-9">
                  {q.options.map((opt, optIdx) => (
                    <label
                      key={optIdx}
                      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors
                        ${answers[q.question_id] === opt
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}
                    >
                      <input
                        type="radio"
                        name={q.question_id}
                        value={opt}
                        checked={answers[q.question_id] === opt}
                        onChange={() => setAnswer(q.question_id, opt)}
                        className="text-blue-600"
                      />
                      <span className="text-sm">{opt}</span>
                    </label>
                  ))}
                </div>
              ) : (
                /* CODING / TEXT textarea */
                <div className="ml-9">
                  <Textarea
                    placeholder={
                      q.type === 'CODING'
                        ? 'Write your code or solution here...'
                        : 'Write your answer here...'
                    }
                    value={answers[q.question_id] ?? ''}
                    onChange={(e) => setAnswer(q.question_id, e.target.value)}
                    className={`min-h-36 ${q.type === 'CODING' ? 'font-mono text-sm' : ''}`}
                  />
                </div>
              )}
            </Card>
          ))}

          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={isSubmitting || answered < total}
          >
            {isSubmitting
              ? 'Submitting…'
              : answered < total
                ? `Answer all questions to submit (${total - answered} remaining)`
                : 'Submit Assessment'}
          </Button>
        </form>
      </div>
    </div>
  );
};
