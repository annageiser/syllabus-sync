"""
Base parser class with shared AI extraction logic for all file format parsers.

This module provides common functionality for extracting events from syllabus
documents using Google Vertex AI, including calendar week conversion and
multilingual date parsing.
"""

import json
from datetime import datetime, timedelta
import re
import os
from config import config

# Support both Vertex AI and Google AI SDK
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel as VertexModel
    HAS_VERTEX = True
except ImportError:
    HAS_VERTEX = False

try:
    import google.generativeai as genai
    HAS_GOOGLE_AI = True
except ImportError:
    HAS_GOOGLE_AI = False


class BaseParser:
    """
    Base class for all document parsers.
    
    Provides shared AI-powered event extraction logic that can be used by
    PDF, Excel, Word, and HTML parsers.
    """
    
    def __init__(self):
        """
        Initialize the base parser with Vertex AI or Google AI configuration.
        """
        self.use_vertex = False
        self.api_key = config.GEMINI_API_KEY
        
        if self.api_key:
            if not HAS_GOOGLE_AI:
                raise RuntimeError("google-generativeai package not installed")
            if config.DEBUG:
                print("Initializing with Google AI SDK (API Key)")
            genai.configure(api_key=self.api_key)
            model_name = config.GEMINI_MODEL
            self.model = genai.GenerativeModel(model_name)
            self.source = f"Gemini Cloud AI ({model_name})"
        elif config.GOOGLE_CLOUD_PROJECT:
            if not HAS_VERTEX:
                raise RuntimeError("google-cloud-aiplatform package not installed")
            if config.DEBUG:
                print(f"Initializing with Vertex AI (Project: {config.GOOGLE_CLOUD_PROJECT})")
            vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.VERTEX_AI_LOCATION)
            self.model = VertexModel(config.GEMINI_MODEL)
            self.use_vertex = True
            self.source = f"Vertex AI ({config.GEMINI_MODEL})"
        else:
            if config.DEBUG:
                print("WARNING: No AI configuration found. Using HEURISTIC OFFLINE EXTRACTION only.")
            self.model = None
            self.source = "Local Heuristic (Offline)"
        
        self.current_year = config.DEFAULT_YEAR
    
    def convert_calendar_week_to_date(self, week_num: int, year: int = None) -> str:
        """
        Convert a calendar week number to a date (Monday of that week).
        
        Args:
            week_num: Calendar week number (1-53)
            year: Year for the calendar week (defaults to config.DEFAULT_YEAR)
            
        Returns:
            Date string in YYYY-MM-DD format (Monday of the specified week)
            
        Example:
            >>> convert_calendar_week_to_date(15, 2026)
            '2026-04-06'  # Monday of week 15, 2026
        """
        if year is None:
            year = self.current_year
        
        # ISO 8601: Week 1 is the first week with a Thursday
        # Get the Monday of week 1
        jan_4 = datetime(year, 1, 4)
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        
        # Calculate the Monday of the target week
        target_monday = week_1_monday + timedelta(weeks=week_num - 1)
        
        return target_monday.strftime("%Y-%m-%d")
    
    def extract_events_with_ai(self, text_content: str) -> list:
        """
        Extract events from text content using Vertex AI.
        
        This method sends the document text to Gemini AI with an enhanced prompt
        that extracts module names, supports calendar weeks, handles multiple
        languages, and identifies various event types.
        
        Args:
            text_content: The text content of the document to analyze
            
        Returns:
            List of event dictionaries with keys:
                - module (str): Course/module name or code
                - title (str): Event title
                - date (str): Date in YYYY-MM-DD format
                - type (str): Event type (lecture, assignment, exam, etc.)
                - description (str): Additional notes/description
                
        Raises:
            Exception: If AI processing fails
        """
        prompt = f"""
Analyze the uploaded academic syllabus or course schedule document and extract ALL events, deadlines, assignments, exams, lectures, and important dates.

**EXTRACT THE FOLLOWING FIELDS FOR EACH EVENT:**

1. **module**: The course name, module name, or course code (e.g., "CS101", "Mathematics", "Introduction to AI", "BIT BC1", "Statistics and Probability"). This is usually at the top of document or in headers. If multiple modules are in one document, extract the module for each specific event.

2. **title**: The name of the specific event, assignment, lecture, exam, or homework (e.g., "Midterm Exam", "Homework 3", "Lecture on Recursion", "Project Submission")

3. **date** OR **calendar_week**: Extract the date information in one of these formats:
   - If a specific date is given: Use YYYY-MM-DD format
   - If a calendar week is given (CW, KW, Week, Woche, Semaine, Settimana, etc.), extract the week number
   - If only a month/day is given without a year, assume year {self.current_year}
   
   **MULTILINGUAL DATE KEYWORDS TO RECOGNIZE:**
   - English: Date, Week, Calendar Week, CW
   - German: Datum, Woche, Kalenderwoche, KW
   - French: Date, Semaine, Semaine calendaire, SC
   - Italian: Data, Settimana, Settimana di calendario
   - Spanish: Fecha, Semana

4. **type**: Classify the event as one of the following:
   - "lecture" - Class sessions, lessons, seminars
   - "assignment" - Homework, assignments, exercises to complete
   - "exam" - Exams, tests, quizzes, assessments
   - "test" - Same as exam (will be normalized)
   - "homework" - Same as assignment (will be normalized)
   - "project" - Projects, presentations, group work submissions
   - "event" - Other events (office hours, reviews, etc.)

5. **description**: Optional. Any additional notes, topics covered, chapters, weighting percentage, or other relevant information.

**OUTPUT FORMAT:**

Return ONLY valid JSON (no markdown formatting, no ```json blocks):

[
  {{
    "module": "CS101",
    "title": "Midterm Exam",
    "date": "2026-03-15",
    "type": "exam",
    "description": "Chapters 1-5, 30% of final grade"
  }},
  {{
    "module": "Mathematics",
    "title": "Homework 3",
    "calendar_week": 12,
    "type": "assignment",
    "description": "Linear algebra problems"
  }},
  {{
    "module": "BIT BC1",
    "title": "Lecture: Introduction to Databases",
    "date": "2026-02-18",
    "type": "lecture",
    "description": "SQL basics, relational model"
  }}
]

**IMPORTANT RULES:**
- Extract ALL events from the document, don't skip any
- If the module name appears once at the top, use it for all events
- For calendar weeks (CW/KW), provide the week number in "calendar_week" field
- For lecture series, extract individual lectures if dates are provided
- Normalize types: "test" → "exam", "homework" → "assignment"
- If an event has NO date or calendar week, skip it
- Return an empty list [] if no events are found

Do not include markdown formatting. Return only the JSON array.
"""
        
    def heuristic_extraction(self, text: str) -> list:
        """
        Offline heuristic extraction using regex and keyword matching.
        This is a free fallback for when AI extraction is unavailable.
        """
        events = []
        lines = text.split('\n')
        
        # Try to find module name at the top
        module_name = ""
        for i in range(min(10, len(lines))):
            line = lines[i].strip()
            if "Module" in line or "Course" in line or "Program:" in line:
                module_name = line.split(":")[-1].strip()
                break
        
        # Common date patterns
        # 1. DD Month (e.g., 20 Feb, 27 February)
        months = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)'
        date_pattern = re.compile(rf'(\d{{1,2}})\.?\s+{months}', re.IGNORECASE)
        
        # 2. DD.MM. (European format)
        euro_pattern = re.compile(r'(\d{1,2})\.(\d{1,2})\.')
        
        # 3. YYYY-MM-DD
        iso_pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

        # 4. KW/CW (Calendar Week)
        week_pattern = re.compile(r'(KW|CW|Week|Woche)\s*(\d{1,2})', re.IGNORECASE)

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            found_date = None
            
            # Check for patterns
            match = date_pattern.search(line)
            if match:
                day = match.group(1)
                month_str = match.group(2)[:3].capitalize()
                try:
                    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, 
                                 "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                    month = month_map.get(month_str, 1)
                    found_date = f"{self.current_year}-{month:02d}-{int(day):02d}"
                except: pass
            
            if not found_date:
                match = euro_pattern.search(line)
                if match:
                    day, month = match.groups()
                    found_date = f"{self.current_year}-{int(month):02d}-{int(day):02d}"
            
            if not found_date:
                match = iso_pattern.search(line)
                if match:
                    found_date = match.group(0)
            
            if not found_date:
                match = week_pattern.search(line)
                if match:
                    try:
                        week_num = int(match.group(2))
                        found_date = self.convert_calendar_week_to_date(week_num)
                    except: pass

            if found_date:
                # Use the rest of the line or the next line as title
                # Filter out the date/week part from the line
                title = line
                for pattern in [date_pattern, euro_pattern, iso_pattern, week_pattern]:
                    title = pattern.sub('', title).strip()
                
                # If title is too short, look at next line
                if len(title) < 5 and i + 1 < len(lines):
                    title = f"{title} {lines[i+1].strip()}".strip()
                
                # Determine type
                event_type = "lecture"
                if any(k in title.lower() for k in ["exam", "test", "klausur", "quiz"]):
                    event_type = "exam"
                elif any(k in title.lower() for k in ["assignment", "due", "moodle", "submission", "homework"]):
                    event_type = "assignment"
                elif any(k in title.lower() for k in ["project", "presentation"]):
                    event_type = "project"
                
                events.append({
                    "module": module_name,
                    "title": title[:100],
                    "date": found_date,
                    "type": event_type,
                    "description": line
                })

        return events

    def extract_events_with_ai(self, text_content: str) -> list:
        """
        Extract events from text content using Vertex AI or Google AI.
        Falls back to heuristic extraction if AI fails or is not configured.
        
        Returns:
            List of event dictionaries.
        """
        # Fallback if no AI model is configured
        if not self.model:
            if config.DEBUG:
                print("No AI model configured, using heuristic extraction")
            self.source = "Local Heuristic (Offline)"
            return self.heuristic_extraction(text_content)

        prompt = f"""
Analyze the document and extract ALL events (assignments, exams, lectures).
Return ONLY a JSON array:
[
  {{
    "module": "CS101",
    "title": "Midterm Exam",
    "date": "2026-03-15",
    "type": "exam",
    "description": "..."
  }}
]
Rules:
- dates: YYYY-MM-DD or use "calendar_week": 12
- types: lecture, assignment, exam, project, event
- multilingual support
"""
        
        try:
            # Combine prompt and content for better compatibility
            full_prompt = f"{prompt}\n\nDOCKET CONTENT:\n{text_content}"
            response = self.model.generate_content(full_prompt)
            response_text = response.text.strip()
            
            if config.DEBUG:
                print(f"AI Response (first 100 chars): {response_text[:100]}...")
            
            # Clean up markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[-1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[-1].split("```")[0]
            
            response_text = response_text.strip()
            
            # Parse JSON
            try:
                events = json.loads(response_text)
                if not isinstance(events, list): 
                    self.source = "Local Heuristic (Fallback: Invalid JSON structure)"
                    return self.heuristic_extraction(text_content)
                
                normalized_events = []
                for event in events:
                    if not isinstance(event, dict): continue
                    
                    normalized_event = {
                        "module": event.get("module", ""),
                        "title": event.get("title", "Untitled"),
                        "type": (event.get("type", "event")).lower(),
                        "description": event.get("description", "")
                    }
                    
                    date_str = event.get("date")
                    calendar_week = event.get("calendar_week")
                    
                    if date_str:
                        normalized_event["date"] = date_str
                    elif calendar_week:
                        try:
                            normalized_event["date"] = self.convert_calendar_week_to_date(int(calendar_week))
                        except: continue
                    else: continue
                    
                    normalized_events.append(normalized_event)
                
                # self.source is already set in __init__ for the AI case
                return normalized_events
                
            except json.JSONDecodeError:
                if config.DEBUG: print("JSON Decode Error, falling back to heuristic")
                self.source = "Local Heuristic (Fallback: JSON Parse Error)"
                return self.heuristic_extraction(text_content)
                
        except Exception as e:
            if config.DEBUG:
                print(f"AI Extraction failed: {e}")
                print("Falling back to HEURISTIC OFFLINE EXTRACTION")
            self.source = f"Local Heuristic (Fallback: AI Error - {str(e)})"
            return self.heuristic_extraction(text_content)
