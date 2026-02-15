from icalendar import Calendar, Event, Alarm
from datetime import datetime, timedelta
import os

class ICSGenerator:
    """
    Generate ICS (iCalendar) files from event data.
    
    Converts structured event dictionaries into RFC 5545 compliant ICS format
    for import into calendar applications.
    """
    
    def generate(self, events: list) -> bytes:
        """
        Generate an ICS calendar file from a list of events.
        
        Args:
            events: List of event dictionaries with keys:
                - title (str): Event title
                - date (str): Date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
                - type (str): Event type (e.g., 'assignment', 'exam', 'lecture')
                - description (str, optional): Event description
                
        Returns:
            Bytes containing the ICS file content
            
        Raises:
            ValueError: If events list is invalid
        """
        if not isinstance(events, list):
            raise ValueError("Events must be a list")
        
        cal = Calendar()
        cal.add('prodid', '-//Syllabus-Sync//mxm.dk//')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', 'Syllabus Events')
        cal.add('x-wr-caldesc', 'Events extracted from academic syllabus')

        for item in events:
            if not isinstance(item, dict):
                continue
                
            event = Event()
            
            # Title with module name
            title = item.get('title', 'Untitled Event')
            module = item.get('module', '')

            full_title = f"{module} - {title}" if module else title
            event.add('summary', full_title)
            
            # Description
            description_parts = []
            if item.get('description'):
                description_parts.append(item['description'])
            if item.get('type'):
                description_parts.append(f"Type: {item['type'].capitalize()}")
            if module and module not in full_title:
                description_parts.append(f"Module: {module}")
            if item.get('location'):
                description_parts.append(f"Location: {item['location']}")
            if description_parts:
                event.add('description', '\n'.join(description_parts))
            
            # Date/time parsing
            start_date = item.get('date')
            start_time = item.get('start_time') or item.get('time')
            end_time = item.get('end_time')

            if start_date:
                try:
                    if 'T' in start_date:
                        dt_start = datetime.fromisoformat(start_date)
                    else:
                        base_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                        if start_time:
                            dt_start = datetime.combine(base_date, datetime.strptime(start_time, "%H:%M").time())
                        else:
                            dt_start = base_date

                    if isinstance(dt_start, datetime):
                        if end_time:
                            dt_end = datetime.combine(dt_start.date(), datetime.strptime(end_time, "%H:%M").time())
                            if dt_end <= dt_start:
                                dt_end = dt_start + timedelta(hours=1)
                        else:
                            dt_end = dt_start + timedelta(hours=1)
                    else:
                        dt_end = dt_start

                    event.add('dtstart', dt_start)
                    event.add('dtend', dt_end)

                    if item.get('location'):
                        event.add('location', item.get('location'))

                    if item.get('type'):
                        event.add('categories', [item['type'].upper()])

                    event_type = item.get('type', '').lower()
                    priority = item.get('priority')
                    if priority is None:
                        if event_type == 'exam':
                            priority = 1
                        elif event_type in ['assignment', 'project']:
                            priority = 3 if event_type == 'project' else 5
                        else:
                            priority = 9
                    event.add('priority', priority)

                    reminder_minutes = []
                    for reminder in item.get('reminders') or []:
                        try:
                            minutes = int(reminder)
                            if minutes > 0:
                                reminder_minutes.append(minutes)
                        except (TypeError, ValueError):
                            continue

                    if reminder_minutes:
                        # Ensure deterministic order and avoid duplicates
                        unique_minutes = sorted(set(reminder_minutes))
                        base_dt = dt_start if isinstance(dt_start, datetime) else datetime.combine(dt_start, datetime.min.time())
                        for minutes_before in unique_minutes:
                            alarm = Alarm()
                            alarm.add('action', 'DISPLAY')
                            alarm.add('description', f'Reminder: {title}')
                            alarm.add('trigger', timedelta(minutes=-minutes_before))
                            event.add_component(alarm)
                    elif event_type in ['assignment', 'exam', 'project']:
                        # Preserve default reminder when user did not set any
                        alarm = Alarm()
                        alarm.add('action', 'DISPLAY')
                        alarm.add('description', f'Reminder: {title}')
                        alarm.add('trigger', timedelta(days=-1))
                        event.add_component(alarm)

                    recurrence = item.get('recurrence')
                    if isinstance(recurrence, dict) and recurrence.get('freq'):
                        freq = recurrence.get('freq', '').upper()
                        rrule_parts = [f'FREQ={freq}']
                        if recurrence.get('count'):
                            rrule_parts.append(f'COUNT={recurrence.get("count")}')
                        if recurrence.get('until'):
                            rrule_parts.append(f'UNTIL={recurrence.get("until")}')
                        event.add('rrule', ';'.join(rrule_parts))

                    event.add('uid', f'{hash(f"{title}{start_date}{start_time}")}@syllabus-sync.app')
                    event.add('dtstamp', datetime.now())

                    cal.add_component(event)

                except ValueError as e:
                    print(f"WARNING: Skipping event '{title}' due to invalid date/time format: {start_date} ({e})")
                    continue

        return cal.to_ical()
