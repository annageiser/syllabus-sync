import React, { useState } from 'react';

interface Event {
    title: string;
    date: string;
    type: string;
    description?: string;
    module?: string;
}

interface EventTableProps {
    events: Event[];
    onUpdate: (index: number, updatedEvent: Event) => void;
    onDelete: (index: number) => void;
}

const EventTable: React.FC<EventTableProps> = ({ events, onUpdate, onDelete }) => {
    if (events.length === 0) return null;

    return (
        <div className="overflow-x-auto mt-8">
            <table className="min-w-full bg-white border border-gray-200 shadow-sm rounded-lg" role="table" aria-label="Event list">
                <thead className="bg-gray-50">
                    <tr>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Module</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                        <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                    {events.map((event, index) => (
                        <tr key={index} className="hover:bg-gray-50 transition-colors">
                            <td className="px-6 py-4">
                                <input
                                    type="text"
                                    value={event.module || ''}
                                    onChange={(e) => onUpdate(index, { ...event, module: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                    placeholder="Course code..."
                                    aria-label={`Module name ${index + 1}`}
                                />
                            </td>
                            <td className="px-6 py-4">
                                <input
                                    type="text"
                                    value={event.title}
                                    onChange={(e) => onUpdate(index, { ...event, title: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                    aria-label={`Event title ${index + 1}`}
                                />
                            </td>
                            <td className="px-6 py-4">
                                <input
                                    type="date"
                                    value={event.date}
                                    onChange={(e) => onUpdate(index, { ...event, date: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                    aria-label={`Event date ${index + 1}`}
                                />
                            </td>
                            <td className="px-6 py-4">
                                <select
                                    value={event.type}
                                    onChange={(e) => onUpdate(index, { ...event, type: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                    aria-label={`Event type ${index + 1}`}
                                >
                                    <option value="lecture">Lecture</option>
                                    <option value="assignment">Assignment</option>
                                    <option value="exam">Exam</option>
                                    <option value="project">Project</option>
                                    <option value="event">Event</option>
                                </select>
                            </td>
                            <td className="px-6 py-4">
                                <input
                                    type="text"
                                    value={event.description || ''}
                                    onChange={(e) => onUpdate(index, { ...event, description: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                    placeholder="Optional notes..."
                                    aria-label={`Event description ${index + 1}`}
                                />
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button
                                    onClick={() => onDelete(index)}
                                    className="text-red-600 hover:text-red-900 transition-colors"
                                    aria-label={`Delete event ${event.title}`}
                                >
                                    Delete
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default EventTable;
