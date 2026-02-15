'use client';

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { saveAs } from 'file-saver';
import FileUploader from '../components/FileUploader';
import EventTable from '../components/EventTable';
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
  const [mounted, setMounted] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Load theme from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'dark' | 'light';
    if (savedTheme) {
      setTheme(savedTheme);
    }
    setMounted(true);
  }, []);

  // Sync theme with document and localStorage
  useEffect(() => {
    if (!mounted) return;
    const root = window.document.documentElement;
    if (theme === 'light') {
      root.classList.add('light');
    } else {
      root.classList.remove('light');
    }
    localStorage.setItem('theme', theme);
  }, [theme, mounted]);

  // Mouse tracking for "Fancy" glow
  useEffect(() => {
    if (!mounted) return;
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [mounted]);

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  const normalizeEvent = (evt: any): Event => {
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

  const handleFileUpload = async (file: File) => {
    setLoading(true);
    setStatusMessage('Uploading & parsing...');
    setError(null);
    setLastFile(file);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      const normalizedEvents: Event[] = (response.data.events || []).map(normalizeEvent);
      const validationError = validateEvents(normalizedEvents);
      if (validationError) {
        setError(validationError);
        return;
      }
      setEvents(normalizedEvents);
      setExtractionSource(response.data.extraction_source);
      setProcessingMode(response.data.processing_mode);
      setFallbackReason(response.data.fallback_reason);
      setExtractionWarning(response.data.extraction_warning);
      setStatusMessage(response.data.processing_mode === 'heuristic' ? 'Parsed via fallback (heuristic)' : 'Parsed via AI');
    } catch (err: any) {
      console.error(err);
      let errorMessage = 'Failed to process file. Please try again.';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          errorMessage = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (detail?.error) {
          errorMessage = detail.error;
        }
      } else if (err.message === 'Network Error') {
        errorMessage = 'Server unreachable. Is the backend running?';
      }
      setError(errorMessage);
      setStatusMessage('Error');
    } finally {
      setLoading(false);
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

      const payload = events.map(evt => ({ ...evt, time: `${evt.time}:00` }));

      const response = await axios.post(`${API_URL}/generate-ics`, payload, {
        responseType: 'blob',
        headers: {
          'Accept': 'text/calendar',
        }
      });

      const blob = new Blob([response.data], { type: 'text/calendar' });
      saveAs(blob, 'syllabus-events.ics');
    } catch (err: any) {
      console.error("Export Error:", err);
      let message = 'Failed to generate ICS file.';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          message = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else if (typeof detail === 'string') {
          message = detail;
        }
      }
      setError(message);
    }
  };

  if (!mounted) {
    return <div className="min-h-screen bg-[#020617]" />; // Stable initial render
  }

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

      <div className="max-w-6xl mx-auto px-4 relative z-10">
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

        <div className="max-w-4xl mx-auto space-y-16">
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
              {lastFile && !loading && (
                <button
                  onClick={handleRetry}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-100 border border-slate-600 hover:border-indigo-400 hover:text-indigo-200 transition-all"
                >
                  Retry last upload
                </button>
              )}
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

                <button
                  onClick={handleExportICS}
                  className="fancy-button flex items-center px-10 py-5 bg-indigo-600 text-white font-black rounded-2xl hover:scale-[1.05] active:scale-95 shadow-2xl shadow-indigo-600/30 transition-all"
                >
                  <Download className="mr-3 h-6 w-6" /> Export to Calendar
                </button>
              </div>

              <div className="relative">
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
