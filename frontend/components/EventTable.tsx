import React, { useState } from 'react';

interface Event {
    title: string;
    date: string;
    type: string;
    // Add more fields as needed: time, room, description
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
            <table className="min-w-full bg-white border border-gray-200 shadow-sm rounded-lg">
                <thead className="bg-gray-50">
                    <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                    {events.map((event, index) => (
                        <tr key={index}>
                            <td className="px-6 py-4 whitespace-nowrap">
                                <input
                                    type="text"
                                    value={event.title}
                                    onChange={(e) => onUpdate(index, { ...event, title: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                />
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                                <input
                                    type="date"
                                    value={event.date}
                                    onChange={(e) => onUpdate(index, { ...event, date: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                />
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                                <select
                                    value={event.type}
                                    onChange={(e) => onUpdate(index, { ...event, type: e.target.value })}
                                    className="w-full border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                                >
                                    <option value="lecture">Lecture</option>
                                    <option value="assignment">Assignment</option>
                                    <option value="exam">Exam</option>
                                    <option value="event">Event</option>
                                </select>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button
                                    onClick={() => onDelete(index)}
                                    className="text-red-600 hover:text-red-900"
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
