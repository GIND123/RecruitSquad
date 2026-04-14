import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Send, CheckCircle2, Loader2, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatContext {
  candidate_name: string;
  job_title: string;
  question_count: number;
}

export const BehavioralChat = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const [context, setContext] = useState<ChatContext | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load context then fire the opening question
  useEffect(() => {
    if (!token) return;

    fetch(`${BASE}/api/chat/${token}`)
      .then((r) => {
        if (!r.ok) throw new Error('Invalid interview link');
        return r.json() as Promise<ChatContext>;
      })
      .then((ctx) => {
        setContext(ctx);
        // Kick off the interview — empty message + empty history = first question
        return sendMessage('', [], ctx);
      })
      .catch((err: unknown) => {
        toast.error(err instanceof Error ? err.message : 'Failed to load interview');
        setIsInitializing(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const sendMessage = async (
    text: string,
    currentHistory: Message[],
    ctx?: ChatContext,
  ) => {
    setIsSending(true);
    const history = currentHistory.map((m) => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
    }));

    try {
      const res = await fetch(`${BASE}/api/chat/${token}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history }),
      });
      if (!res.ok) throw new Error('Failed to send message');

      const data = await res.json() as {
        reply: string;
        is_complete: boolean;
        candidate_name: string;
        job_title: string;
      };

      if (!context && ctx) {
        setContext({ ...ctx, candidate_name: data.candidate_name, job_title: data.job_title });
      }

      setMessages((prev) => {
        const updated = text
          ? [...prev, { role: 'user' as const, content: text }, { role: 'assistant' as const, content: data.reply }]
          : [...prev, { role: 'assistant' as const, content: data.reply }];
        return updated;
      });

      if (data.is_complete) setIsComplete(true);
    } catch {
      toast.error('Connection error — please try again.');
    } finally {
      setIsSending(false);
      setIsInitializing(false);
    }
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text || isSending || isComplete) return;
    setInput('');
    sendMessage(text, messages);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isInitializing) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-10 h-10 text-blue-600 animate-spin mx-auto mb-3" />
          <p className="text-gray-600">Starting your interview…</p>
        </div>
      </div>
    );
  }

  if (!context) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <h1 className="text-2xl font-bold mb-2">Invalid Link</h1>
          <p className="text-gray-600 mb-6">This interview link is invalid or has expired.</p>
          <Button onClick={() => navigate('/jobs')}>Browse Jobs</Button>
        </Card>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md w-full mx-4 p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Interview Complete!</h1>
          <p className="text-gray-600 mb-6">
            Thank you, <strong>{context.candidate_name}</strong>. Your behavioral interview for{' '}
            <strong>{context.job_title}</strong> has been recorded. Our team will be in touch soon.
          </p>
          <Button onClick={() => navigate('/jobs')}>Browse More Jobs</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 px-4 flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-3">
            <MessageSquare className="w-6 h-6 opacity-80" />
            <div>
              <h1 className="font-semibold text-lg leading-tight">Behavioral Interview</h1>
              <p className="text-sm opacity-80">
                {context.job_title} · {context.candidate_name}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto py-6 px-4">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-sm'
                    : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-sm'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {isSending && messages.length > 0 && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1 items-center h-5">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="bg-white border-t px-4 py-3 flex-shrink-0">
        <div className="max-w-3xl mx-auto flex gap-2">
          <Input
            placeholder="Type your answer…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending || isComplete}
            className="flex-1"
            autoFocus
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isSending || isComplete}
            size="icon"
            className="shrink-0"
          >
            {isSending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
        <p className="max-w-3xl mx-auto text-xs text-gray-400 mt-1.5 text-center">
          Answer each question naturally — the interviewer will guide you through all{' '}
          {context.question_count} questions.
        </p>
      </div>
    </div>
  );
};
