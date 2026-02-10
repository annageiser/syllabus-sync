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
            
            # Prepend module name to title if available
            if module:
                full_title = f"{module} - {title}"
            else:
                full_title = title
            
            event.add('summary', full_title)
            
            # Description
            description_parts = []
            if item.get('description'):
                description_parts.append(item['description'])
            if item.get('type'):
                description_parts.append(f"Type: {item['type'].capitalize()}")
            if module and module not in full_title:
                # If module wasn't in title, add to description
                description_parts.append(f"Module: {module}")
            if description_parts:
                event.add('description', '\n'.join(description_parts))
            
            # Date parsing
            start_date = item.get('date')

            if start_date:
                try:
                    # Handle full datetime or just date
                    if 'T' in start_date:
                        dt_start = datetime.fromisoformat(start_date)
                    else:
                        # Parse as date only
                        dt_start = datetime.strptime(start_date, "%Y-%m-%d").date()
                        
                    event.add('dtstart', dt_start)
                    
                    # Assume 1 hour duration if no end time, or all day if date only
                    if isinstance(dt_start, datetime):
                        event.add('dtend', dt_start + timedelta(hours=1))
                    else:
                        event.add('dtend', dt_start)  # All day event
                    
                    # Add event type as category
                    if item.get('type'):
                        event.add('categories', [item['type'].upper()])
                    
                    # Set priority based on event type
                    event_type = item.get('type', '').lower()
                    if event_type == 'exam':
                        event.add('priority', 1)  # High priority
                    elif event_type in ['assignment', 'project']:
                        event.add('priority', 5)  # Medium priority
                    else:
                        event.add('priority', 9)  # Low priority
                    
                    # Add reminder for assignments and exams (groundwork for future feature)
                    if event_type in ['assignment', 'exam', 'project']:
                        alarm = Alarm()
                        alarm.add('action', 'DISPLAY')
                        alarm.add('description', f'Reminder: {title}')
                        # Reminder 1 day before
                        alarm.add('trigger', timedelta(days=-1))
                        event.add_component(alarm)
                    
                    # Add unique identifier
                    event.add('uid', f'{hash(f"{title}{start_date}")}@syllabus-sync.app')
                    event.add('dtstamp', datetime.now())
                    
                    cal.add_component(event)
                    
                except ValueError as e:
                    # Skip events with invalid dates
                    print(f"WARNING: Skipping event '{title}' due to invalid date format: {start_date} ({e})")
                    continue

        return cal.to_ical()
