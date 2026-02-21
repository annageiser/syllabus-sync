import React, { useMemo } from 'react';

interface Event {
    date: string; // YYYY-MM-DD
}

interface YearHeatmapProps {
    events: Event[];
}

const YearHeatmap: React.FC<YearHeatmapProps> = ({ events }) => {
    const { year, days, maxCount } = useMemo(() => {
        if (!events || events.length === 0) {
            return { year: new Date().getFullYear(), days: [], maxCount: 0 };
        }

        // Find the most common year among events
        const yearCounts: Record<number, number> = {};
        events.forEach(e => {
            if (e.date) {
                const y = parseInt(e.date.split('-')[0], 10);
                if (!isNaN(y)) {
                    yearCounts[y] = (yearCounts[y] || 0) + 1;
                }
            }
        });

        let targetYear = new Date().getFullYear();
        let maxYearCount = 0;
        for (const [y, count] of Object.entries(yearCounts)) {
            if (count > maxYearCount) {
                maxYearCount = count;
                targetYear = parseInt(y, 10);
            }
        }

        // Aggregate events by date
        const dateCounts: Record<string, number> = {};
        let maxCnt = 0;
        events.forEach(e => {
            if (e.date && e.date.startsWith(targetYear.toString())) {
                dateCounts[e.date] = (dateCounts[e.date] || 0) + 1;
                if (dateCounts[e.date] > maxCnt) {
                    maxCnt = dateCounts[e.date];
                }
            }
        });

        // Generate all days of the target year
        const days = [];
        const startDate = new Date(targetYear, 0, 1);
        const endDate = new Date(targetYear, 11, 31);

        for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
            const dateStr = d.toISOString().split('T')[0];
            days.push({
                date: dateStr,
                count: dateCounts[dateStr] || 0
            });
        }

        return { year: targetYear, days, maxCount: maxCnt };
    }, [events]);

    if (days.length === 0) return null;

    const getColor = (count: number) => {
        if (count === 0) return 'bg-slate-200 dark:bg-slate-800';
        if (maxCount === 1) return 'bg-indigo-500';
        
        const intensity = count / maxCount;
        if (intensity <= 0.25) return 'bg-indigo-300 dark:bg-indigo-900';
        if (intensity <= 0.5) return 'bg-indigo-400 dark:bg-indigo-700';
        if (intensity <= 0.75) return 'bg-indigo-500 dark:bg-indigo-600';
        return 'bg-indigo-600 dark:bg-indigo-500';
    };

    const startDayOfWeek = new Date(year, 0, 1).getDay();

    return (
        <div className="mt-8 glass p-6 rounded-2xl animate-slide-up mb-8">
            <h3 className="text-lg font-black mb-4 flex items-center gap-2">
                <span className="text-indigo-500">Event Activity</span>
                <span className="text-slate-400 font-medium text-sm">({year})</span>
            </h3>
            <div className="overflow-x-auto pb-4">
                <div className="min-w-max">
                    <div className="flex gap-1">
                        {(() => {
                            const weeks = [];
                            let currentWeek: (typeof days[0] | null)[] = [];
                            
                            // Pad the first week
                            for (let i = 0; i < startDayOfWeek; i++) {
                                currentWeek.push(null);
                            }
                            
                            days.forEach(day => {
                                currentWeek.push(day);
                                if (currentWeek.length === 7) {
                                    weeks.push(currentWeek);
                                    currentWeek = [];
                                }
                            });
                            
                            if (currentWeek.length > 0) {
                                while (currentWeek.length < 7) {
                                    currentWeek.push(null);
                                }
                                weeks.push(currentWeek);
                            }
                            
                            return weeks.map((week, wIndex) => (
                                <div key={wIndex} className="flex flex-col gap-1">
                                    {week.map((day, dIndex) => {
                                        if (!day) return <div key={`empty-${wIndex}-${dIndex}`} className="w-3 h-3" />;
                                        return (
                                            <div 
                                                key={day.date}
                                                className={`w-3 h-3 rounded-sm ${getColor(day.count)} transition-all duration-200 hover:ring-2 hover:ring-indigo-400 cursor-pointer relative group`}
                                            >
                                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10 bg-slate-800 text-white text-xs py-1 px-2 rounded shadow-xl whitespace-nowrap pointer-events-none">
                                                    <span className="font-bold">{day.date}</span>: {day.count} event{day.count !== 1 ? 's' : ''}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            ));
                        })()}
                    </div>
                    <div className="flex items-center gap-2 mt-6 text-xs font-medium text-slate-500">
                        <span>Less</span>
                        <div className="w-3 h-3 rounded-sm bg-slate-200 dark:bg-slate-800"></div>
                        <div className="w-3 h-3 rounded-sm bg-indigo-300 dark:bg-indigo-900"></div>
                        <div className="w-3 h-3 rounded-sm bg-indigo-400 dark:bg-indigo-700"></div>
                        <div className="w-3 h-3 rounded-sm bg-indigo-500 dark:bg-indigo-600"></div>
                        <div className="w-3 h-3 rounded-sm bg-indigo-600 dark:bg-indigo-500"></div>
                        <span>More</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default YearHeatmap;
