import React, { useMemo } from 'react';

interface Event {
  title: string;
  date: string;
  type: string;
  description?: string;
  module?: string;
}

interface EventHeatmapProps {
  events: Event[];
}

type DayBucket = {
  date: string; // YYYY-MM-DD
  count: number;
};

// Utility to parse a date string safely
const parseDate = (value: string | undefined | null): Date | null => {
  if (!value) return null;
  // Accept YYYY-MM-DD or full ISO
  const base = value.includes('T') ? value : `${value}T00:00:00`;
  const d = new Date(base);
  return isNaN(d.getTime()) ? null : d;
};

// Build a continuous range of days from minDate to maxDate
const buildDateRange = (min: Date, max: Date): string[] => {
  const days: string[] = [];
  const cursor = new Date(min);
  cursor.setHours(0, 0, 0, 0);
  const end = new Date(max);
  end.setHours(0, 0, 0, 0);

  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = `${cursor.getMonth() + 1}`.padStart(2, '0');
    const day = `${cursor.getDate()}`.padStart(2, '0');
    days.push(`${year}-${month}-${day}`);
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
};

const getIntensityClass = (count: number, maxCount: number): string => {
  if (maxCount === 0 || count === 0) return 'bg-slate-800/40 border-slate-700/40';
  const ratio = count / maxCount;
  if (ratio > 0.75) return 'bg-emerald-500 border-emerald-400';
  if (ratio > 0.5) return 'bg-emerald-400/80 border-emerald-300/80';
  if (ratio > 0.25) return 'bg-emerald-300/60 border-emerald-200/60';
  return 'bg-emerald-200/40 border-emerald-100/40';
};

const weekdayLabels = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

const EventHeatmap: React.FC<EventHeatmapProps> = ({ events }) => {
  const { buckets, weeks, maxCount, minDate, maxDate, totalEvents } = useMemo(() => {
    const parsed: { raw: Event; date: Date; key: string }[] = [];

    for (const ev of events) {
      const d = parseDate(ev.date);
      if (!d) continue;
      d.setHours(0, 0, 0, 0);
      const year = d.getFullYear();
      const month = `${d.getMonth() + 1}`.padStart(2, '0');
      const day = `${d.getDate()}`.padStart(2, '0');
      const key = `${year}-${month}-${day}`;
      parsed.push({ raw: ev, date: d, key });
    }

    if (!parsed.length) {
      return {
        buckets: new Map<string, DayBucket>(),
        weeks: [] as string[][],
        maxCount: 0,
        minDate: null as Date | null,
        maxDate: null as Date | null,
        totalEvents: 0,
      };
    }

    // Determine range
    let min = parsed[0].date;
    let max = parsed[0].date;
    for (const p of parsed) {
      if (p.date < min) min = p.date;
      if (p.date > max) max = p.date;
    }

    // Pad a bit so graph feels spacious (one week before/after)
    const minPadded = new Date(min);
    minPadded.setDate(minPadded.getDate() - 3);
    const maxPadded = new Date(max);
    maxPadded.setDate(maxPadded.getDate() + 3);

    const range = buildDateRange(minPadded, maxPadded);

    const bucketMap = new Map<string, DayBucket>();
    for (const key of range) {
      bucketMap.set(key, { date: key, count: 0 });
    }

    let maxCountLocal = 0;
    for (const p of parsed) {
      const year = p.date.getFullYear();
      const month = `${p.date.getMonth() + 1}`.padStart(2, '0');
      const day = `${p.date.getDate()}`.padStart(2, '0');
      const key = `${year}-${month}-${day}`;
      const bucket = bucketMap.get(key);
      if (!bucket) continue;
      bucket.count += 1;
      if (bucket.count > maxCountLocal) maxCountLocal = bucket.count;
    }

    // Group into weeks (GitHub-style: columns = weeks, rows = weekdays)
    const weeks: string[][] = [];
    let currentWeek: string[] = [];

    for (const key of range) {
      const [y, m, d] = key.split('-').map(Number);
      const date = new Date(y, (m || 1) - 1, d || 1);
      const jsWeekday = date.getDay(); // 0 = Sunday
      const weekdayIndex = (jsWeekday + 6) % 7; // 0 = Monday

      if (currentWeek.length === 0 && weekdayIndex > 0) {
        // pad start of first week
        for (let i = 0; i < weekdayIndex; i++) {
          currentWeek.push(''); // empty slots
        }
      }

      // Ensure week has correct position for this weekday
      while (currentWeek.length < weekdayIndex) {
        currentWeek.push('');
      }

      currentWeek.push(key);

      if (weekdayIndex === 6) {
        weeks.push(currentWeek);
        currentWeek = [];
      }
    }

    if (currentWeek.length) {
      weeks.push(currentWeek);
    }

    return {
      buckets: bucketMap,
      weeks,
      maxCount: maxCountLocal,
      minDate: min,
      maxDate: max,
      totalEvents: parsed.length,
    };
  }, [events]);

  if (!weeks.length || !minDate || !maxDate || totalEvents === 0) {
    return null;
  }

  const formatDisplayDate = (dateStr: string) => {
    const [y, m, d] = dateStr.split('-').map(Number);
    if (!y || !m || !d) return dateStr;
    const date = new Date(y, m - 1, d);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  };

  const spanText = `${formatDisplayDate(
    minDate.toISOString().slice(0, 10),
  )} – ${formatDisplayDate(maxDate.toISOString().slice(0, 10))}`;

  return (
    <div className="mb-10">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold">Workload Heatmap</h3>
          <p className="text-xs text-slate-500">
            Darker blocks = more items due on that day ({spanText})
          </p>
        </div>
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-500">
          <span className="mr-1">Light</span>
          <div className="flex gap-1">
            {[0.2, 0.4, 0.6, 0.8].map((ratio, idx) => (
              <div
                key={idx}
                className="w-4 h-3 rounded-sm border"
                style={{
                  backgroundColor: `rgba(16, 185, 129, ${ratio})`,
                  borderColor: 'rgba(110, 231, 183, 0.6)',
                }}
              />
            ))}
          </div>
          <span className="ml-1">Heavy</span>
        </div>
      </div>

      <div className="flex gap-3">
        {/* Weekday labels */}
        <div className="flex flex-col justify-between py-1 text-[10px] text-slate-500 mr-1">
          {weekdayLabels.map((label, idx) => (
            <div
              key={idx}
              className="h-4 flex items-center justify-end pr-1"
            >
              {label}
            </div>
          ))}
        </div>

        {/* Heatmap grid */}
        <div className="overflow-x-auto">
          <div className="flex gap-1">
            {weeks.map((week, colIdx) => (
              <div key={colIdx} className="flex flex-col gap-1">
                {weekdayLabels.map((_, rowIdx) => {
                  const slot = week[rowIdx] ?? '';
                  const bucket = slot ? buckets.get(slot) : undefined;
                  const count = bucket?.count ?? 0;
                  const baseClasses =
                    'w-4 h-4 rounded-[3px] border transition-colors duration-150';
                  const intensityClass = getIntensityClass(count, maxCount);
                  const title =
                    count > 0
                      ? `${formatDisplayDate(bucket!.date)} • ${count} item${
                          count > 1 ? 's' : ''
                        } due`
                      : '';

                  return (
                    <div
                      key={rowIdx}
                      className={
                        slot
                          ? `${baseClasses} ${intensityClass}`
                          : `${baseClasses} bg-transparent border-transparent`
                      }
                      title={title}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventHeatmap;

