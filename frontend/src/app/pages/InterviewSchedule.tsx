import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { CheckCircle2, Calendar, MapPin, Clock, AlertCircle, Briefcase } from 'lucide-react';
import { toast } from 'sonner';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface ScheduleContext {
  candidate_id: string;
  candidate_name: string;
  job_title: string;
  job_team: string;
  job_locations: string[];
  already_confirmed: boolean;
  confirmed_slot: string | null;
}

// Generate available slots: next 7 business days × 3 times per day
function generateSlots(): { label: string; iso: string }[] {
  const slots: { label: string; iso: string }[] = [];
  const times = [
    { label: '10:00 AM', hour: 10 },
    { label: '2:00 PM',  hour: 14 },
    { label: '4:00 PM',  hour: 16 },
  ];

  let day = new Date();
  day.setHours(0, 0, 0, 0);
  let added = 0;

  while (added < 7) {
    day = new Date(day.getTime() + 24 * 60 * 60 * 1000);
    const dow = day.getDay();
    if (dow === 0 || dow === 6) continue; // skip weekends

    const dateLabel = day.toLocaleDateString('en-US', {
      weekday: 'long', month: 'short', day: 'numeric',
    });

    for (const t of times) {
      const d = new Date(day);
      d.setHours(t.hour, 0, 0, 0);
      slots.push({
        label: `${dateLabel} · ${t.label}`,
        iso:   d.toISOString(),
      });
    }
    added++;
  }
  return slots;
}

export const InterviewSchedule = () => {
  const { candidateId } = useParams<{ candidateId: string }>();

  const [ctx, setCtx]           = useState<ScheduleContext | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError]        = useState('');
  const [selected, setSelected]  = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [confirmedLabel, setConfirmedLabel] = useState('');

  const slots = generateSlots();
  const tz    = Intl.DateTimeFormat().resolvedOptions().timeZone;

  useEffect(() => {
    if (!candidateId) return;
    fetch(`${BASE}/api/jobs/schedule/${candidateId}`)
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail ?? 'Link not found');
        }
        return res.json() as Promise<ScheduleContext>;
      })
      .then((data) => {
        setCtx(data);
        if (data.already_confirmed) {
          setConfirmed(true);
          setConfirmedLabel(data.confirmed_slot ?? '');
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [candidateId]);

  const handleConfirm = async () => {
    if (!selected) { toast.error('Please pick a time slot'); return; }
    const slotObj = slots.find((s) => s.iso === selected);
    setIsSubmitting(true);
    try {
      const res = await fetch(`${BASE}/api/jobs/schedule/${candidateId}/confirm`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ slot: selected, timezone: tz }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Confirmation failed');
      }
      setConfirmed(true);
      setConfirmedLabel(slotObj?.label ?? selected);
      toast.success('Interview slot confirmed!');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to confirm slot');
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
          <p className="text-gray-500">{error}</p>
        </Card>
      </div>
    );
  }

  // ── Already confirmed ────────────────────────────────────────────────────────
  if (confirmed) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Interview Confirmed!</h1>
          <p className="text-gray-600 mb-4">
            {ctx?.candidate_name ? `Hi ${ctx.candidate_name}, your` : 'Your'} interview for{' '}
            <strong>{ctx?.job_title}</strong> has been booked.
          </p>
          {confirmedLabel && (
            <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800 flex items-center justify-center gap-2">
              <Calendar className="w-4 h-4 shrink-0" />
              <span>{confirmedLabel}</span>
            </div>
          )}
          <p className="text-xs text-gray-500 mt-4">
            A confirmation email with the video link has been sent to you.
          </p>
        </Card>
      </div>
    );
  }

  if (!ctx) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-8">
        <div className="container mx-auto px-4 max-w-2xl">
          <p className="text-sm opacity-75 mb-1">Interview Scheduling</p>
          <h1 className="text-2xl md:text-3xl font-bold mb-1">{ctx.job_title}</h1>
          {ctx.candidate_name && (
            <p className="opacity-80">Hi {ctx.candidate_name}, pick a slot that works for you</p>
          )}
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 max-w-2xl space-y-6">
        {/* Job info */}
        <Card className="p-4">
          <div className="flex flex-wrap gap-4 text-sm text-gray-600">
            {ctx.job_team && (
              <span className="flex items-center gap-1.5">
                <Briefcase className="w-4 h-4" /> {ctx.job_team}
              </span>
            )}
            {ctx.job_locations?.length > 0 && (
              <span className="flex items-center gap-1.5">
                <MapPin className="w-4 h-4" /> {ctx.job_locations.join(', ')}
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <Clock className="w-4 h-4" /> 60 min interview
            </span>
          </div>
        </Card>

        {/* Slot picker */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-1">Choose a Time Slot</h2>
          <p className="text-sm text-gray-500 mb-4">
            All times shown in your local timezone ({tz}).
          </p>

          <Label className="sr-only">Available slots</Label>
          <div className="space-y-2">
            {slots.map((slot) => (
              <label
                key={slot.iso}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors
                  ${selected === slot.iso
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}
              >
                <input
                  type="radio"
                  name="slot"
                  value={slot.iso}
                  checked={selected === slot.iso}
                  onChange={() => setSelected(slot.iso)}
                  className="text-blue-600"
                />
                <Calendar className="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm">{slot.label}</span>
              </label>
            ))}
          </div>

          <Button
            className="w-full mt-6"
            size="lg"
            onClick={handleConfirm}
            disabled={!selected || isSubmitting}
          >
            {isSubmitting ? 'Confirming…' : 'Confirm This Slot'}
          </Button>

          <p className="text-xs text-gray-400 text-center mt-3">
            A video link will be emailed to you after confirmation.
            Can't make any of these times? Reply to your invite email.
          </p>
        </Card>
      </div>
    </div>
  );
};
