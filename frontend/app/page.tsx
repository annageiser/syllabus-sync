'use client';

import React, { useState } from 'react';
import axios from 'axios';
import { saveAs } from 'file-saver';
import FileUploader from '../components/FileUploader';
import EventTable from '../components/EventTable';
import { Calendar, Download, RefreshCw } from 'lucide-react';

interface Event {
  title: string;
  date: string;
  type: string;
}

export default function Home() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (file: File) => {
    setLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setEvents(response.data.events);
    } catch (err) {
      console.error(err);
      setError('Failed to process file. Please try again.');
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
      console.log("Sending events to backend:", events);

      const response = await axios.post('http://localhost:8000/generate-ics', events);
      const blob = new Blob([response.data.ics_content], { type: 'text/calendar;charset=utf-8' });
      saveAs(blob, 'syllabus-events.ics');
    } catch (err: any) {
      console.error("Export Error:", err);
      if (err.response) {
        console.error("Response Data:", err.response.data);
        console.error("Response Status:", err.response.status);
        setError(`Failed to generate ICS file: ${JSON.stringify(err.response.data)}`);
      } else {
        setError('Failed to generate ICS file.');
      }
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

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {events.length > 0 && (
            <div className="mt-8">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-800">Extracted Events</h2>
                <button
                  onClick={handleExportICS}
                  className="flex items-center px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
                >
                  <Download className="mr-2 h-4 w-4" /> Export to Calendar (.ics)
                </button>
              </div>
              <EventTable
                events={events}
                onUpdate={handleUpdateEvent}
                onDelete={handleDeleteEvent}
              />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
