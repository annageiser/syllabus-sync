'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios, { AxiosError } from 'axios';
import { saveAs } from 'file-saver';
import FileUploader from '../components/FileUploader';
import EventTable from '../components/EventTable';
import YearHeatmap from '../components/YearHeatmap';
import {
  Calendar,
  Download,
  RefreshCw,
  Cpu,
  ShieldCheck,
  Moon,
  Sun,
  Sparkles,
  MousePointer2
} from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const ASYNC_SIZE_THRESHOLD = 2 * 1024 * 1024; // 2MB threshold to auto-switch to async
const ASYNC_TIMEOUT_MS = 90_000; // 90s safety timeout for streaming
const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Singapore',
  'Australia/Sydney',
];

interface Event {
  title: string;
  date: string;
  time: string;
  type: string;
  description?: string;
  module?: string;
  reminders?: number[];
  confidence?: number;
  low_confidence_fields?: string[];
}

type RawEvent = Partial<Event> & {
  start_time?: string;
};

interface UploadResponse {
  events?: RawEvent[];
  extraction_source?: string;
  source?: string;
  processing_mode?: string;
  fallback_reason?: string | null;
  extraction_warning?: string | null;
  status?: string;
  progress?: string;
  error?: string | null;
  filename?: string;
}

export default function Home() {
  const [events, setEvents] = useState<Event[]>([]);
  const [extractionSource, setExtractionSource] = useState<string | null>(null);
  const [processingMode, setProcessingMode] = useState<string | null>(null);
  const [fallbackReason, setFallbackReason] = useState<string | null>(null);
  const [extractionWarning, setExtractionWarning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('Idle');
  const [error, setError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<File | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [timezone, setTimezone] = useState<string>('UTC');
  const [useAsyncUpload, setUseAsyncUpload] = useState<boolean>(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const asyncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load theme from localStorage on mount (client-only)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const savedTheme = localStorage.getItem('theme') as 'dark' | 'light';
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);

  // Default timezone from browser when available
  useEffect(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) setTimezone(tz);
    } catch {
      // Ignore if Intl is unavailable
    }
  }, []);

  // Load events from localStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const savedEvents = localStorage.getItem('syllabus_events');
    if (savedEvents) {
      try {
        const parsed = JSON.parse(savedEvents);
        if (Array.isArray(parsed)) {
          setEvents(parsed);
        }
      } catch (e) {
        console.error('Failed to parse saved events', e);
      }
    }
  }, []);

  // Save events to localStorage whenever they change
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem('syllabus_events', JSON.stringify(events));
  }, [events]);

  // Cleanup any open SSE streams on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (asyncTimeoutRef.current) {
        clearTimeout(asyncTimeoutRef.current);
      }
    };
  }, []);

  // Sync theme with document and localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const root = window.document.documentElement;
    if (theme === 'light') {
      root.classList.add('light');
      root.classList.remove('dark');
    } else {
      root.classList.remove('light');
      root.classList.add('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Mouse tracking for "Fancy" glow
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  const normalizeEvent = (evt: RawEvent): Event => {
    const safeTitle = (evt?.title || '').trim() || 'Untitled';
    const safeType = (evt?.type || 'event').toLowerCase();
    const safeDate = (evt?.date || '').slice(0, 10);
    const safeTime = (() => {
      const t = (evt?.time || evt?.start_time || '').trim();
      if (/^\d{2}:\d{2}/.test(t)) return t.slice(0, 5);
      return '09:00';
    })();
    return {
      title: safeTitle,
      date: safeDate,
      time: safeTime,
      type: safeType,
      description: evt?.description || '',
      module: evt?.module || '',
      reminders: Array.isArray(evt?.reminders) ? evt.reminders : [],
      confidence: typeof evt?.confidence === 'number' ? evt.confidence : 0.5,
      low_confidence_fields: Array.isArray(evt?.low_confidence_fields) ? evt.low_confidence_fields : [],
    };
  };

  const validateEvents = (list: Event[]): string | null => {
    for (const [idx, evt] of list.entries()) {
      if (!evt.title.trim()) return `Row ${idx + 1}: title is required`;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(evt.date)) return `Row ${idx + 1}: invalid date format`;
      if (!/^\d{2}:\d{2}$/.test(evt.time)) return `Row ${idx + 1}: invalid time format`;
      if (!evt.type) return `Row ${idx + 1}: type is required`;
    }
    return null;
  };

  const cleanupStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (asyncTimeoutRef.current) {
      clearTimeout(asyncTimeoutRef.current);
      asyncTimeoutRef.current = null;
    }
  }, []);

  const applyParsedEvents = (data: UploadResponse, originLabel?: string): boolean => {
    const normalizedEvents: Event[] = (data?.events || []).map(normalizeEvent);
    const validationError = validateEvents(normalizedEvents);
    if (validationError) {
      setError(validationError);
      return false;
    }
    setEvents(prev => [...prev, ...normalizedEvents]);
    setExtractionSource(data?.extraction_source || data?.source || originLabel || null);
    setProcessingMode(data?.processing_mode || null);
    setFallbackReason(data?.fallback_reason || null);
    setExtractionWarning(data?.extraction_warning || null);
    setStatusMessage((data?.processing_mode || '') === 'heuristic' ? 'Parsed via fallback (heuristic)' : 'Parsed via AI');
    setError(null);
    return true;
  };

  const extractErrorMessage = (err: unknown, fallback: string): string => {
    if (axios.isAxiosError(err)) {
      const detail = (err as AxiosError<{ detail?: unknown; error?: string }>).response?.data?.detail;
      if (Array.isArray(detail)) {
        const parts = detail.map((d) => {
          if (typeof d === 'object' && d && 'msg' in d && typeof (d as { msg?: string }).msg === 'string') {
            return (d as { msg?: string }).msg as string;
          }
          return JSON.stringify(d);
        });
        return parts.join('; ');
      }
      if (typeof detail === 'string') return detail;
      if (detail && typeof detail === 'object' && 'error' in (detail as Record<string, unknown>)) {
        const maybeError = (detail as { error?: unknown }).error;
        if (typeof maybeError === 'string') return maybeError;
      }
      const directError = (err as AxiosError<{ error?: string }>).response?.data?.error;
      if (typeof directError === 'string') return directError;
    }
    if (err instanceof Error) return err.message;
    return fallback;
  };

  const handleSyncUpload = async (file: File) => {
    cleanupStream();
    setLoading(true);
    setStatusMessage('Uploading & parsing...');
    setError(null);
    setJobId(null);
    setJobProgress(null);
    setLastFile(file);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      applyParsedEvents(response.data, response.data?.extraction_source || 'sync');
    } catch (err: unknown) {
      console.error(err);
      const errorMessage = extractErrorMessage(err, 'Failed to process file. Please try again.');
      setError(errorMessage === 'Network Error' ? 'Server unreachable. Is the backend running?' : errorMessage);
      setStatusMessage('Error');
    } finally {
      setLoading(false);
    }
  };

  const handleAsyncUpload = async (file: File) => {
    cleanupStream();
    setLoading(true);
    setStatusMessage('Enqueueing async job...');
    setError(null);
    setLastFile(file);
    setJobProgress('queued');
    setFallbackReason(null);
    setExtractionWarning(null);
    setExtractionSource(null);
    setProcessingMode(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_URL}/upload/async`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const newJobId = response.data?.job_id;
      if (!newJobId) {
        throw new Error('Async upload missing job id');
      }

      setJobId(newJobId);
      setStatusMessage('Job queued, waiting for stream...');

      const streamUrl = `${API_URL}/upload/stream/${newJobId}`;
      const evtSource = new EventSource(streamUrl);
      eventSourceRef.current = evtSource;

      asyncTimeoutRef.current = setTimeout(() => {
        setError('Async processing timed out. Falling back to sync.');
        setJobProgress('timeout');
        cleanupStream();
        setLoading(false);
        handleSyncUpload(file);
      }, ASYNC_TIMEOUT_MS);

      evtSource.onmessage = (event) => {
        try {
          const payload: UploadResponse = JSON.parse(event.data);
          setJobProgress(payload.progress || payload.status || null);
          setStatusMessage(`Async: ${payload.status || ''}${payload.progress ? ` (${payload.progress})` : ''}`.trim());

          if (payload.error) {
            setError(payload.error);
            cleanupStream();
            setLoading(false);
            handleSyncUpload(file);
            return;
          }

          if (payload.status === 'completed' && payload.events) {
            applyParsedEvents(payload, payload.source || 'async');
            setJobId(null);
            setJobProgress('completed');
            setStatusMessage('Async parse complete');
            cleanupStream();
            setLoading(false);
          } else if (payload.status === 'failed') {
            setError(payload.error || 'Async parsing failed');
            cleanupStream();
            setLoading(false);
            handleSyncUpload(file);
          }
        } catch (streamErr) {
          console.error('Stream parse error', streamErr);
          setError('Streaming data error. Falling back to sync.');
          cleanupStream();
          setLoading(false);
          handleSyncUpload(file);
        }
      };

      evtSource.onerror = () => {
        setError('Streaming connection lost. Falling back to sync.');
        cleanupStream();
        setLoading(false);
        handleSyncUpload(file);
      };
    } catch (err: unknown) {
      console.error(err);
      const errorMessage = extractErrorMessage(err, 'Failed to start async processing. Trying sync...');
      setError(errorMessage);
      setStatusMessage('Falling back to sync...');
      cleanupStream();
      setLoading(false);
      await handleSyncUpload(file);
    }
  };

  const handleFileUpload = async (file: File) => {
    const shouldUseAsync = useAsyncUpload || file.size > ASYNC_SIZE_THRESHOLD;
    if (shouldUseAsync) {
      await handleAsyncUpload(file);
    } else {
      await handleSyncUpload(file);
    }
  };

  const handleRetry = () => {
    if (lastFile) {
      handleFileUpload(lastFile);
    }
  };

  const handleExportICS = async () => {
    try {
      if (!events.length) return;

      const validationError = validateEvents(events);
      if (validationError) {
        setError(validationError);
        return;
      }

      const payload = {
        events: events.map(evt => ({ ...evt, time: `${evt.time}:00` })),
        timezone,
      };

      const response = await axios.post(`${API_URL}/generate-ics`, payload, {
        responseType: 'blob',
        headers: {
          'Accept': 'text/calendar',
        }
      });

      const blob = new Blob([response.data], { type: 'text/calendar' });
      saveAs(blob, 'syllabus-events.ics');
    } catch (err: unknown) {
      console.error("Export Error:", err);
      const message = extractErrorMessage(err, 'Failed to generate ICS file.');
      setError(message);
    }
  };

  const timezoneOptions = Array.from(new Set([timezone, ...COMMON_TIMEZONES]));

  return (
    <main className="min-h-screen pb-24 relative overflow-hidden transition-colors duration-500">
      {/* Fancy Dynamic Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div
          className="absolute w-[600px] h-[600px] -top-48 -left-48 bg-indigo-500/10 blur-[120px] rounded-full transition-transform duration-1000 ease-out"
          style={{ transform: `translate(${(mousePos.x - 500) / 40}px, ${(mousePos.y - 500) / 40}px)` }}
        ></div>
        <div
          className="absolute w-[500px] h-[500px] top-[20%] -right-24 bg-purple-500/10 blur-[120px] rounded-full transition-transform duration-1000 ease-out"
          style={{ transform: `translate(${(mousePos.x - 500) / -60}px, ${(mousePos.y - 500) / -60}px)` }}
        ></div>
      </div>

      {/* Mouse Follow Light */}
      <div
        className="fixed pointer-events-none z-0 w-[400px] h-[400px] rounded-full blur-[100px] opacity-10 transition-all duration-300"
        style={{
          left: mousePos.x - 200,
          top: mousePos.y - 200,
          background: 'radial-gradient(circle, var(--accent), transparent 70%)'
        }}
      ></div>

      <div className="w-full px-4 md:px-8 lg:px-12 mx-auto relative z-10">
        {/* Navigation / Header Bar */}
        <nav className="flex justify-between items-center py-8 mb-12 animate-slide-up">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/40">
              <Calendar className="text-white w-6 h-6" />
            </div>
            <span className="text-xl font-black tracking-tighter uppercase hidden sm:inline">SyllabusSync</span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={toggleTheme}
              className="p-3 rounded-2xl glass hover:scale-110 transition-all dark-toggle-icon"
              aria-label="Toggle Theme"
            >
              {theme === 'dark' ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5 text-indigo-600" />}
            </button>
            <div className="hidden md:flex gap-4">
              <span className="flex items-center gap-1.5 text-xs font-bold text-slate-500 uppercase tracking-widest bg-slate-500/10 px-4 py-2 rounded-full border border-slate-500/10">
                <ShieldCheck size={14} className="text-emerald-500" /> Privacy Secure
              </span>
            </div>
          </div>
        </nav>

        {/* Hero Section */}
        <header className="text-center mb-20 animate-slide-up" style={{ animationDelay: '100ms' }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm font-bold tracking-tight mb-8">
            <Sparkles size={16} className="animate-pulse" /> AI Extraction 2.0
          </div>
          <h1 className="text-6xl md:text-8xl font-black mb-6 tracking-tight leading-none">
            Your Schedule, <br />
            <span className="text-indigo-500 italic">Intelligently</span> Synced.
          </h1>
          <p className="text-lg md:text-xl max-w-2xl mx-auto text-slate-400 font-medium leading-relaxed">
            Upload your chaotic syllabus and let our AI transform it into a professional calendar. No data storage, no tracking, just speed.
          </p>
        </header>

        <div className="w-full space-y-16">
          {/* Main Action Area */}
          <section id="upload-zone" className="animate-slide-up" style={{ animationDelay: '200ms' }}>
            <FileUploader onFileUpload={handleFileUpload} />

            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm font-semibold text-slate-400">
              <span className="px-3 py-1 rounded-full bg-slate-500/10 border border-slate-500/20">Status: {statusMessage}</span>
              {processingMode && (
                <span className="px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">Mode: {processingMode}</span>
              )}
              {fallbackReason && (
                <span className="px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400">Fallback: {fallbackReason}</span>
              )}
              {extractionWarning && (
                <span className="px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400">Warning: {extractionWarning}</span>
              )}
              {jobId && (
                <span className="px-3 py-1 rounded-full bg-slate-500/10 border border-slate-500/20 text-slate-200">Async job: {jobProgress || 'queued'}</span>
              )}
              {lastFile && !loading && (
                <button
                  onClick={handleRetry}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-100 border border-slate-600 hover:border-indigo-400 hover:text-indigo-200 transition-all"
                >
                  Retry last upload
                </button>
              )}
              <label className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-500/10 border border-slate-500/20 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useAsyncUpload}
                  onChange={(e) => setUseAsyncUpload(e.target.checked)}
                  className="accent-indigo-500"
                />
                <span>Use async streaming (auto for files &gt; 2MB)</span>
              </label>
            </div>

            {loading && (
              <div className="mt-12 flex flex-col items-center gap-6 text-indigo-500 animate-pulse">
                <div className="relative">
                  <RefreshCw className="animate-spin h-10 w-10" />
                  <div className="absolute inset-0 h-10 w-10 blur-xl bg-indigo-500/30"></div>
                </div>
                <span className="font-bold text-lg tracking-widest uppercase">Analyzing Document Layers...</span>
                <span className="text-sm text-slate-400">This may take up to 30s for large PDFs.</span>
              </div>
            )}

            {error && (
              <div className="mt-8 p-6 rounded-2xl glass border-rose-500/30 bg-rose-500/5 text-rose-500 text-center font-bold" role="alert">
                {error}
                {lastFile && (
                  <div className="mt-3">
                    <button
                      onClick={handleRetry}
                      className="px-4 py-2 rounded-xl bg-rose-500/10 border border-rose-500/40 text-rose-100 hover:border-rose-300 transition"
                    >
                      Retry last file
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Results Area */}
          {events.length > 0 && (
            <section id="results" className="animate-slide-up" style={{ animationDelay: '300ms' }}>
              <div className="flex flex-col md:flex-row justify-between items-end md:items-center mb-10 gap-6">
                <div>
                  <h2 className="text-4xl font-bold mb-2">Schedule Draft</h2>
                  <p className="text-slate-500 flex items-center gap-2 font-medium">
                    <Cpu size={14} /> Processed via <span className="text-indigo-500 font-bold">{extractionSource}</span>
                    {processingMode && (
                      <span className="ml-2 px-2 py-1 rounded-lg bg-slate-500/10 text-xs font-bold uppercase tracking-wide">{processingMode}</span>
                    )}
                    {fallbackReason && (
                      <span className="ml-2 px-2 py-1 rounded-lg bg-amber-500/10 text-amber-400 text-xs font-bold">Fallback: {fallbackReason}</span>
                    )}
                    {extractionWarning && (
                      <span className="ml-2 px-2 py-1 rounded-lg bg-rose-500/10 text-rose-400 text-xs font-bold">Warning: {extractionWarning}</span>
                    )}
                  </p>
                </div>

                <div className="flex flex-col md:flex-row items-stretch md:items-center gap-4">
                  <label className="flex flex-col text-sm font-semibold text-slate-400">
                    Timezone
                    <select
                      className="mt-1 bg-slate-900/70 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 shadow-inner focus:outline-none focus:border-indigo-400"
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                    >
                      {timezoneOptions.map((tz) => (
                        <option key={tz} value={tz}>{tz}</option>
                      ))}
                    </select>
                  </label>

                  <button
                    onClick={() => {
                      if (confirm('Are you sure you want to clear all aggregated events?')) {
                        setEvents([]);
                        localStorage.removeItem('syllabus_events');
                      }
                    }}
                    className="flex items-center px-6 py-5 bg-rose-600/20 text-rose-400 font-black rounded-2xl hover:bg-rose-600/30 active:scale-95 transition-all border border-rose-500/30"
                  >
                    Clear Data
                  </button>

                  <button
                    onClick={handleExportICS}
                    className="fancy-button flex items-center px-10 py-5 bg-indigo-600 text-white font-black rounded-2xl hover:scale-[1.05] active:scale-95 shadow-2xl shadow-indigo-600/30 transition-all"
                  >
                    <Download className="mr-3 h-6 w-6" /> Export to Calendar
                  </button>
                </div>
              </div>

              <div className="relative">
                <YearHeatmap events={events} />
                <EventTable
                  events={events}
                  onUpdate={(i, e) => {
                    const next = [...events];
                    next[i] = e;
                    setEvents(next);
                  }}
                  onDelete={(i) => setEvents(prev => prev.filter((_, idx) => idx !== i))}
                />
              </div>
            </section>
          )}
        </div>
      </div>

      <footer className="mt-32 py-12 text-center text-slate-500 border-t border-white/5 mx-auto max-w-4xl">
        <div className="flex justify-center gap-8 mb-6">
          <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest"><ShieldCheck size={14} /> Stateless</span>
          <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest"><Cpu size={14} /> Gemini Powered</span>
          <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest"><MousePointer2 size={14} /> Interactive</span>
        </div>
        <p className="text-xs opacity-50">&copy; 2026 SyllabusSync AI - Your Data Remains Yours.</p>
      </footer>
    </main>
  );
}
