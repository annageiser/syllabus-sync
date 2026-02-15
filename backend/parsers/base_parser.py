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
import hashlib
import time
import copy
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
        # Simple in-memory cache for AI responses keyed by normalized text content
        self.cache_ttl_seconds = 900  # 15 minutes
        if not hasattr(self.__class__, "_ai_cache"):
            self.__class__._ai_cache = {}
    
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
        normalized_text = text_content.strip()

        prompt = f"""
Analyze the uploaded academic syllabus or course schedule document and extract ALL events, deadlines, assignments, exams, lectures, and important dates.

**EXTRACT THE FOLLOWING FIELDS FOR EACH EVENT:**

1. **module**: Course/module name or code (e.g., "CS101").
2. **title**: Event title (lecture name, assignment, exam, project, etc.).
3. **date** OR **calendar_week**: Use YYYY-MM-DD for exact dates. If only week numbers (CW/KW/Week/Woche/etc.), return "calendar_week".
4. **start_time** and optional **end_time**: 24h HH:MM. If only one time is present, set it as start_time.
5. **location**: Room/building/URL if present.
6. **type**: lecture, assignment, exam, project, event (normalize "test"→exam, "homework"→assignment).
7. **recurrence**: For repeating sessions (e.g., weekly lectures), return {{"freq": "weekly", "count": N}} where N is occurrences if known.
8. **priority**: 1-9 (1 highest). Use 1 for exams, 3 for projects, 5 for assignments, 9 for lectures/events unless weighting hints higher stakes.
9. **description**: Topics, chapters, notes.

**OUTPUT FORMAT:**
Return ONLY valid JSON (no markdown):
[
    {{
        "module": "CS101",
        "title": "Midterm Exam",
        "date": "2026-03-15",
        "start_time": "10:00",
        "type": "exam",
        "priority": 1,
        "location": "Room 201",
        "description": "Ch 1-5",
        "recurrence": null
    }},
    {{
        "module": "CS101",
        "title": "Lecture: Databases",
        "date": "2026-02-18",
        "start_time": "14:00",
        "end_time": "16:00",
        "type": "lecture",
        "location": "Zoom",
        "recurrence": {{"freq": "weekly", "count": 12}}
    }},
    {{
        "module": "CS101",
        "title": "Homework 3",
        "calendar_week": 12,
        "type": "assignment",
        "priority": 5,
        "description": "Linear algebra problems"
    }}
]

Rules: extract ALL events; assume year {self.current_year} when missing; skip entries without any date/week; normalize types; prefer structured outputs with times/locations/recurrence when present. Return [] if none.
"""

        # If no AI model is configured, fall back immediately
        if not self.model:
            if config.DEBUG:
                print("No AI model configured, using heuristic extraction")
            self.source = "Local Heuristic (Offline)"
            return self.heuristic_extraction(text_content)

        cache_key = None
        # Check cache before calling the model
        try:
            cache_input = normalized_text.encode("utf-8")
            cache_hash = hashlib.sha256(cache_input).hexdigest()
            cache_key = (self.source or "local", self.current_year, cache_hash)
            cached = self._ai_cache.get(cache_key)
            if cached:
                ts, cached_events = cached
                if time.time() - ts < self.cache_ttl_seconds:
                    return copy.deepcopy(cached_events)
                else:
                    # Expired
                    self._ai_cache.pop(cache_key, None)
        except Exception:
            # Cache failures should not block parsing
            cache_key = None

        try:
            full_prompt = f"{prompt}\n\nDOCKET CONTENT:\n{text_content}"
            generation_config = {
                "max_output_tokens": 512,
                "temperature": 0.2,
            }

            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            response_text = response.text.strip()

            if config.DEBUG:
                print(f"AI Response (first 100 chars): {response_text[:100]}...")

            # Clean up markdown fences if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[-1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[-1].split("```")[0]

            response_text = response_text.strip()

            try:
                events = json.loads(response_text)
                if not isinstance(events, list):
                    self.source = "Local Heuristic (Fallback: Invalid JSON structure)"
                    return self.heuristic_extraction(text_content)

                normalized_events = []
                for event in events:
                    if not isinstance(event, dict):
                        continue

                    normalized_event = {
                        "module": event.get("module", ""),
                        "title": event.get("title", "Untitled"),
                        "type": (event.get("type", "event")).lower(),
                        "description": event.get("description", ""),
                    }

                    date_str = event.get("date")
                    calendar_week = event.get("calendar_week")

                    if date_str:
                        normalized_event["date"] = date_str
                    elif calendar_week:
                        try:
                            normalized_event["date"] = self.convert_calendar_week_to_date(int(calendar_week))
                        except Exception:
                            continue
                    else:
                        continue

                    # Optional structured fields
                    if event.get("start_time"):
                        normalized_event["start_time"] = event.get("start_time")
                    elif event.get("time"):
                        normalized_event["start_time"] = event.get("time")
                    if event.get("end_time"):
                        normalized_event["end_time"] = event.get("end_time")
                    if event.get("location"):
                        normalized_event["location"] = event.get("location")
                    if event.get("priority"):
                        normalized_event["priority"] = event.get("priority")
                    if event.get("recurrence"):
                        normalized_event["recurrence"] = event.get("recurrence")

                    normalized_events.append(normalized_event)

                # Store successful result in cache
                if cache_key:
                    try:
                        self._ai_cache[cache_key] = (time.time(), copy.deepcopy(normalized_events))
                        # Simple eviction to keep cache bounded
                        if len(self._ai_cache) > 256:
                            oldest_key = min(self._ai_cache.items(), key=lambda kv: kv[1][0])[0]
                            self._ai_cache.pop(oldest_key, None)
                    except Exception:
                        pass

                return normalized_events

            except json.JSONDecodeError:
                if config.DEBUG:
                    print("JSON Decode Error, falling back to heuristic")
                self.source = "Local Heuristic (Fallback: JSON Parse Error)"
                return self.heuristic_extraction(text_content)

        except Exception as e:
            if config.DEBUG:
                print(f"AI Extraction failed: {e}")
                print("Falling back to HEURISTIC OFFLINE EXTRACTION")
            self.source = f"Local Heuristic (Fallback: AI Error - {str(e)})"
            return self.heuristic_extraction(text_content)
        
    def heuristic_extraction(self, text: str) -> list:
        """Offline heuristic extraction using regex and keyword matching."""
        events = []
        lines = text.split('\n')

        module_name = ""
        for i in range(min(10, len(lines))):
            line = lines[i].strip()
            if "Module" in line or "Course" in line or "Program:" in line:
                module_name = line.split(":")[-1].strip()
                break

        months = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)'
        date_pattern = re.compile(rf'(\d{{1,2}})\.?\s+{months}', re.IGNORECASE)
        euro_pattern = re.compile(r'(\d{1,2})\.(\d{1,2})\.')
        iso_pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
        week_pattern = re.compile(r'(KW|CW|Week|Woche)\s*(\d{1,2})', re.IGNORECASE)
        time_pattern = re.compile(r'(\d{1,2}:\d{2})')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            found_date = None
            match = date_pattern.search(line)
            if match:
                day = match.group(1)
                month_str = match.group(2)[:3].capitalize()
                try:
                    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                                 "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                    month = month_map.get(month_str, 1)
                    found_date = f"{self.current_year}-{month:02d}-{int(day):02d}"
                except Exception:
                    pass

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
                    except Exception:
                        pass

            if found_date:
                title = line
                for pattern in [date_pattern, euro_pattern, iso_pattern, week_pattern]:
                    title = pattern.sub('', title).strip()

                if len(title) < 5 and i + 1 < len(lines):
                    title = f"{title} {lines[i+1].strip()}".strip()

                event_type = "lecture"
                lower_title = title.lower()
                if any(k in lower_title for k in ["exam", "test", "klausur", "quiz"]):
                    event_type = "exam"
                elif any(k in lower_title for k in ["assignment", "due", "moodle", "submission", "homework"]):
                    event_type = "assignment"
                elif any(k in lower_title for k in ["project", "presentation"]):
                    event_type = "project"

                start_time = None
                match_time = time_pattern.search(line)
                if match_time:
                    start_time = match_time.group(1)

                location = None
                if any(k in lower_title for k in ["room", "hall", "building", "auditorium", "lab"]):
                    location = title

                events.append({
                    "module": module_name,
                    "title": title[:100],
                    "date": found_date,
                    "start_time": start_time,
                    "location": location,
                    "type": event_type,
                    "description": line
                })

        return events

