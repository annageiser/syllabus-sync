import React from 'react';
import { Trash2, Calendar as CalendarIcon, Tag, FileText, Info, Bell } from 'lucide-react';

interface Event {
    title: string;
    date: string;
    time: string;
    type: string;
    description?: string;
    module?: string;
    reminders?: number[];
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

    const reminderOptions = [
        { value: 10, label: '10m' },
        { value: 60, label: '1h' },
        { value: 180, label: '3h' },
        { value: 1440, label: '1d' },
        { value: 4320, label: '3d' },
        { value: 10080, label: '1w' },
    ];

    return (
        <div className="mt-8 space-y-4">
            <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-3 text-xs font-black text-slate-500 uppercase tracking-[0.2em] opacity-80">
                <div className="col-span-2 flex items-center gap-2"><Tag size={12} /> Module</div>
                <div className="col-span-3 flex items-center gap-2"><FileText size={12} /> Event Title</div>
                <div className="col-span-2 flex items-center gap-2"><CalendarIcon size={12} /> Date</div>
                <div className="col-span-1 flex items-center gap-2"><CalendarIcon size={12} /> Time</div>
                <div className="col-span-2 flex items-center gap-2"><Tag size={12} /> Category</div>
                <div className="col-span-1 flex items-center gap-2"><Info size={12} /> Notes</div>
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

                        <div className="col-span-1 mb-3 md:mb-0">
                            <input
                                id={`event-time-${index}`}
                                type="time"
                                value={event.time}
                                onChange={(e) => onUpdate(index, { ...event, time: e.target.value })}
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

                        <div className="col-span-1 mb-3 md:mb-0">
                            <input
                                id={`event-desc-${index}`}
                                type="text"
                                value={event.description || ''}
                                onChange={(e) => onUpdate(index, { ...event, description: e.target.value })}
                                className="w-full text-sm py-2 px-4 rounded-xl border-0 focus:ring-2 focus:ring-indigo-500 italic opacity-80"
                                placeholder="..."
                            />
                        </div>

                        <div className="col-span-12 mt-3">
                            <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
                                <Bell size={12} /> Reminders
                                <span className="text-[11px] font-medium normal-case tracking-normal text-slate-400">Pick one or more times.</span>
                            </div>
                            <div className="flex flex-wrap gap-2 mt-2">
                                {reminderOptions.map(opt => {
                                    const reminders = event.reminders || [];
                                    const active = reminders.includes(opt.value);
                                    return (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            onClick={() => {
                                                const current = new Set(reminders);
                                                if (active) {
                                                    current.delete(opt.value);
                                                } else {
                                                    current.add(opt.value);
                                                }
                                                onUpdate(index, { ...event, reminders: Array.from(current).sort((a, b) => a - b) });
                                            }}
                                            className={`px-3 py-1 rounded-full border text-xs font-bold transition-all ${active ? 'bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-500/30' : 'bg-white/5 text-slate-400 border-slate-500/30 hover:border-indigo-400/60 hover:text-indigo-400'}`}
                                        >
                                            {opt.label} before
                                        </button>
                                    );
                                })}
                                {(!event.reminders || event.reminders.length === 0) && (
                                    <span className="text-xs text-slate-400 italic">No reminders set</span>
                                )}
                            </div>
                        </div>

                        <div className="col-span-12 md:col-span-1 flex justify-end mt-4 md:mt-0">
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
