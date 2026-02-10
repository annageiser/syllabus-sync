'use client';

import React, { useState } from 'react';
import axios from 'axios';
import { saveAs } from 'file-saver';
import FileUploader from '../components/FileUploader';
import EventTable from '../components/EventTable';
import { Calendar, Download, RefreshCw } from 'lucide-react';

// API configuration from environment variable
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
interface Event {
  title: string;
  date: string;
  type: string;
  description?: string;
  module?: string;
}

export default function Home() {
  const [events, setEvents] = useState<Event[]>([]);
  const [extractionSource, setExtractionSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (file: File) => {
    setLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setEvents(response.data.events);
      setExtractionSource(response.data.extraction_source);
    } catch (err: any) {
      console.error(err);
      let errorMessage = 'Failed to process file. Please try again.';

      if (err.response?.data?.detail) {
        // Use backend error message if available
        errorMessage = typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : 'Failed to process file. Please check the file format.';
      } else if (err.message === 'Network Error') {
        errorMessage = 'Cannot connect to the server. Please ensure the backend is running.';
      }

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateEvent = (index: number, updatedEvent: Event) => {
    const newEvents = [...events];
    newEvents[index] = updatedEvent;
    setEvents(newEvents);
  };

  const handleDeleteEvent = (index: number) => {
    const newEvents = [...events];
    newEvents.splice(index, 1);
    setEvents(newEvents);
  };

  const handleExportICS = async () => {
    try {
      if (!events || events.length === 0) {
        setError('No events to export.');
        return;
      }

      const response = await axios.post(`${API_URL}/generate-ics`, events);
      const blob = new Blob([response.data.ics_content], { type: 'text/calendar;charset=utf-8' });
      saveAs(blob, 'syllabus-events.ics');
    } catch (err: any) {
      console.error("Export Error:", err);

      let errorMessage = 'Failed to generate ICS file.';
      if (err.response?.data?.detail) {
        errorMessage = typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : 'Failed to generate ICS file. Please try again.';
      } else if (err.message === 'Network Error') {
        errorMessage = 'Cannot connect to the server. Please ensure the backend is running.';
      }

      setError(errorMessage);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-10">
          <Calendar className="mx-auto h-12 w-12 text-blue-600" />
          <h1 className="mt-4 text-3xl font-extrabold text-gray-900">Syllabus-Sync</h1>
          <p className="mt-2 text-gray-600">
            Privacy-first tool to convert your syllabus into a calendar.
          </p>
        </div>

        <div className="bg-white shadow sm:rounded-lg p-6">
          <FileUploader onFileUpload={handleFileUpload} />

          {loading && (
            <div className="mt-8 text-center flex justify-center items-center text-blue-600">
              <RefreshCw className="animate-spin mr-2" /> Processing document...
            </div>
          )}

          {error && ( // Corrected the closing parenthesis for the error div
            <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded" role="alert">
              {error}
            </div>
          )}

          {events.length > 0 && (
            <section className="mt-8" aria-labelledby="extracted-events-heading">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
                <div>
                  <h2 id="extracted-events-heading" className="text-xl font-semibold text-gray-800">Extracted Events</h2>
                  {extractionSource && (
                    <p className="text-xs text-gray-500 mt-1">
                      Powered by: <span className="font-medium text-blue-600">{extractionSource}</span>
                    </p>
                  )}
                </div>
                <button
                  onClick={handleExportICS}
                  className="flex items-center px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition w-full sm:w-auto justify-center focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                  aria-label="Export all events to ICS calendar file"
                >
                  <Download className="mr-2 h-4 w-4" aria-hidden="true" /> Export to Calendar (.ics)
                </button>
              </div>
              <EventTable
                events={events}
                onUpdate={handleUpdateEvent}
                onDelete={handleDeleteEvent}
              />
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
