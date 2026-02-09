from icalendar import Calendar, Event, Alarm
from datetime import datetime, timedelta
import os

class ICSGenerator:
    def generate(self, events):
        cal = Calendar()
        cal.add('prodid', '-//Syllabus-Sync//mxm.dk//')
        cal.add('version', '2.0')

        for item in events:
            event = Event()
            event.add('summary', item.get('title', 'Untitled Event'))
            
            start_date = item.get('check_in') # Adjust based on your extraction keys
            if not start_date and item.get('date'):
                 start_date = item.get('date')

            if start_date:
                try:
                    # Handle full datetime or just date
                    if 'T' in start_date:
                        dt_start = datetime.fromisoformat(start_date)
                    else:
                        dt_start = datetime.strptime(start_date, "%Y-%m-%d").date()
                        
                    event.add('dtstart', dt_start)
                    
                    # Assume 1 hour duration if no end time, or all day if date only
                    if isinstance(dt_start, datetime):
                        event.add('dtend', dt_start + timedelta(hours=1))
                    else:
                        event.add('dtend', dt_start) # All day

                    # Add Alarm if specified (mock logic for now)
                    # alarm = Alarm()
                    # ...
                    
                    cal.add_component(event)
                except ValueError:
                    continue

        return cal.to_ical()
