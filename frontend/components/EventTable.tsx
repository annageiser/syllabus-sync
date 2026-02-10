import React, { useState } from 'react';
import { Trash2, Calendar as CalendarIcon, Tag, FileText, Info } from 'lucide-react';

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

    const eventTypes = [
        { value: 'lecture', label: 'Lecture' },
        { value: 'assignment', label: 'Assignment' },
        { value: 'exam', label: 'Exam' },
        { value: 'project', label: 'Project' },
        { value: 'event', label: 'Other' },
    ];

    return (
        <div className="mt-8 space-y-4">
            <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-3 text-xs font-black text-slate-500 uppercase tracking-[0.2em] opacity-80">
                <div className="col-span-2 flex items-center gap-2"><Tag size={12} /> Module</div>
                <div className="col-span-3 flex items-center gap-2"><FileText size={12} /> Event Title</div>
                <div className="col-span-2 flex items-center gap-2"><CalendarIcon size={12} /> Date</div>
                <div className="col-span-2 flex items-center gap-2"><Tag size={12} /> Category</div>
                <div className="col-span-2 flex items-center gap-2"><Info size={12} /> Notes</div>
                <div className="col-span-1"></div>
            </div>

            <div className="space-y-4">
                {events.map((event, index) => (
                    <div
                        key={index}
                        id={`event-row-${index}`}
                        className="glass p-6 md:p-3 md:grid md:grid-cols-12 md:gap-4 items-center animate-slide-up group"
                        style={{ animationDelay: `${index * 50}ms` }}
                    >
                        <div className="col-span-2 mb-3 md:mb-0">
                            <input
                                id={`event-module-${index}`}
                                type="text"
                                value={event.module || ''}
                                onChange={(e) => onUpdate(index, { ...event, module: e.target.value })}
                                className="w-full text-sm py-2 px-4 rounded-xl border-0 focus:ring-2 focus:ring-indigo-500 font-bold"
                                placeholder="Module..."
                            />
                        </div>

                        <div className="col-span-3 mb-3 md:mb-0">
                            <input
                                id={`event-title-${index}`}
                                type="text"
                                value={event.title}
                                onChange={(e) => onUpdate(index, { ...event, title: e.target.value })}
                                className="w-full text-sm py-2 px-4 rounded-xl border-0 focus:ring-2 focus:ring-indigo-500 font-medium"
                            />
                        </div>

                        <div className="col-span-2 mb-3 md:mb-0">
                            <input
                                id={`event-date-${index}`}
                                type="date"
                                value={event.date}
                                onChange={(e) => onUpdate(index, { ...event, date: e.target.value })}
                                className="w-full text-sm py-2 px-4 rounded-xl border-0 focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>

                        <div className="col-span-2 mb-3 md:mb-0">
                            <select
                                id={`event-type-${index}`}
                                value={event.type}
                                onChange={(e) => onUpdate(index, { ...event, type: e.target.value })}
                                className="w-full text-sm py-2 px-4 rounded-xl border-0 focus:ring-2 focus:ring-indigo-500 appearance-none bg-no-repeat bg-[right_1rem_center]"
                            >
                                {eventTypes.map(t => (
                                    <option key={t.value} value={t.value}>{t.label}</option>
                                ))}
                            </select>
                        </div>

                        <div className="col-span-2 mb-3 md:mb-0">
                            <input
                                id={`event-desc-${index}`}
                                type="text"
                                value={event.description || ''}
                                onChange={(e) => onUpdate(index, { ...event, description: e.target.value })}
                                className="w-full text-sm py-2 px-4 rounded-xl border-0 focus:ring-2 focus:ring-indigo-500 italic opacity-80"
                                placeholder="..."
                            />
                        </div>

                        <div className="col-span-1 flex justify-end">
                            <button
                                id={`delete-event-${index}`}
                                onClick={() => onDelete(index)}
                                className="p-3 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded-2xl transition-all"
                                aria-label="Delete Event"
                            >
                                <Trash2 size={20} />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default EventTable;
