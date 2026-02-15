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
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None
        self.extraction_warning = None
        self.last_text_length = 0
        self.last_text_sample = ""
        self.file_type = None
        
        if self.api_key:
            if not HAS_GOOGLE_AI:
                raise RuntimeError("google-generativeai package not installed")
            if config.DEBUG:
                print(f"Initializing with Google AI SDK (API Key present: {bool(self.api_key)}) using model '{config.GEMINI_MODEL}'")
            genai.configure(api_key=self.api_key)
            model_name = config.GEMINI_MODEL
            self.model = genai.GenerativeModel(model_name)
            self.source = f"Gemini Cloud AI ({model_name})"
        elif config.GOOGLE_CLOUD_PROJECT:
            if not HAS_VERTEX:
                raise RuntimeError("google-cloud-aiplatform package not installed")
            if config.DEBUG:
                print(f"Initializing with Vertex AI (Project: {config.GOOGLE_CLOUD_PROJECT}, Model: {config.GEMINI_MODEL})")
            vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.VERTEX_AI_LOCATION)
            self.model = VertexModel(config.GEMINI_MODEL)
            self.use_vertex = True
            self.source = f"Vertex AI ({config.GEMINI_MODEL})"
        else:
            if config.DEBUG:
                print("WARNING: No AI configuration found. Using HEURISTIC OFFLINE EXTRACTION only.")
            self.model = None
            self.source = "Local Heuristic (Offline)"
            self.processing_mode = "heuristic"
            self.fallback_reason = "no_model_configured"
        
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

    def _strip_markdown_fences(self, text: str) -> str:
        """Remove common markdown fences around JSON blocks."""
        if "```json" in text:
            return text.split("```json", 1)[1].split("```", 1)[0]
        if "```" in text:
            return text.split("```", 1)[1].split("```", 1)[0]
        return text

    def _extract_first_json_array(self, text: str) -> str | None:
        """Extract the first JSON array using a simple bracket counter."""
        start = text.find("[")
        if start == -1:
            return None
        depth = 0
        for idx, ch in enumerate(text[start:], start=start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return None

    def _close_unbalanced_delimiters(self, text: str) -> str:
        """Close any unbalanced brackets/braces to handle truncated output."""
        opens = text.count("[") - text.count("]")
        if opens > 0:
            text += "]" * opens
        brace_opens = text.count("{") - text.count("}")
        if brace_opens > 0:
            text += "}" * brace_opens
        return text

    def _try_parse_json(self, raw_text: str):
        """Attempt to parse JSON with light repair passes; returns (events, attempts)."""
        attempts = []

        def attempt(label: str, candidate: str):
            try:
                return json.loads(candidate), label
            except json.JSONDecodeError as exc:
                attempts.append(f"{label}: {exc}")
                return None, None

        cleaned = self._strip_markdown_fences(raw_text).strip()
        events, label = attempt("raw", cleaned)
        if events is not None:
            return events, label

        extracted = self._extract_first_json_array(cleaned)
        if extracted:
            events, label = attempt("extracted_array", extracted)
            if events is not None:
                return events, label

        no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", extracted or cleaned)
        if no_trailing_commas != cleaned:
            events, label = attempt("trim_trailing_commas", no_trailing_commas)
            if events is not None:
                return events, label

        balanced = self._close_unbalanced_delimiters(no_trailing_commas)
        if balanced != no_trailing_commas:
            events, label = attempt("close_unbalanced", balanced)
            if events is not None:
                return events, label

        return None, attempts

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").replace("\r", " ").replace("\n", " ")).strip()

    def _clean_description(self, description: str) -> str:
        cleaned = self._normalize_whitespace(description)
        cleaned = re.sub(r"^[\-\*]\s*", "", cleaned)
        return cleaned.strip(" -")

    def _title_from_description(self, description: str) -> str:
        snippet = self._clean_description(description)
        parts = re.split(r"[\.\n;]\s*", snippet)
        candidate = parts[0] if parts else snippet
        candidate = re.sub(r"^(week|lecture|class|session)\s*\d*[:\-]?\s*", "", candidate, flags=re.IGNORECASE)
        return candidate[:90].strip(" -:") or snippet[:90]

    def _clean_title(self, title: str, description: str | None = None) -> str:
        cleaned = self._normalize_whitespace(title)
        cleaned = re.sub(r"^[\-\*]\s*", "", cleaned)
        cleaned = re.sub(r"^(week|lecture|class|session)\s*\d*[:\-]?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\d+[\.:\)]\s*", "", cleaned)
        cleaned = cleaned.strip(" -:;")

        generic_titles = {"lecture", "class", "session", "event"}
        if (not cleaned or cleaned.lower() in generic_titles) and description:
            cleaned = self._title_from_description(description)

        if len(cleaned) > 90:
            cleaned = cleaned[:90].rstrip(" ,;:") + "..."

        if not cleaned and description:
            cleaned = self._title_from_description(description)

        return cleaned or "Untitled"

    def _clean_event_fields(self, event: dict) -> dict:
        event = dict(event)
        event["title"] = self._clean_title(event.get("title", ""), event.get("description"))
        if event.get("description"):
            event["description"] = self._clean_description(event["description"])
        return event

    def _evaluate_confidence(self, event: dict, source: str) -> tuple[float, list]:
        score = 0.5
        low_fields = []

        title = event.get("title", "").strip()
        if title and len(title) > 8:
            score += 0.05
        else:
            low_fields.append("title")

        date_val = event.get("date")
        if date_val and re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_val)):
            score += 0.3
        else:
            low_fields.append("date")

        evt_type = (event.get("type") or "").lower()
        if evt_type in {"lecture", "assignment", "exam", "project", "event"}:
            score += 0.05
        else:
            low_fields.append("type")

        time_val = event.get("time") or event.get("start_time")
        if time_val and re.match(r"^\d{2}:\d{2}(:\d{2})?$", str(time_val)):
            score += 0.05
        else:
            low_fields.append("time")

        if event.get("description"):
            score += 0.05

        if source == "heuristic":
            score -= 0.1
        if self.fallback_reason:
            score -= 0.05

        score = max(0.0, min(1.0, score))
        if score > 0.6:
            low_fields = [f for f in low_fields if f != "title"]
        return score, low_fields
    
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
        self.last_text_length = len(normalized_text)
        self.last_text_sample = normalized_text[:500]

        if config.DEBUG:
            ftype = getattr(self, "file_type", "unknown") or "unknown"
            print(f"[extract_events_with_ai] file_type={ftype} len={self.last_text_length} sample={self.last_text_sample!r}")

        if self.last_text_length < 30 and not getattr(self, "extraction_warning", None):
            self.extraction_warning = "low_text_quality"

        system_prompt = """
You are a JSON emitter. Output ONLY valid JSON. No markdown, no extra text.
Return a JSON array of event objects. If you cannot find events, return an empty JSON array [] and nothing else.
"""

        prompt = f"""
Analyze the uploaded academic syllabus or course schedule document and extract ALL events, deadlines, assignments, exams, lectures, and important dates.

Schema (array of objects):
- module: string
- title: concise summary of the event topic (avoid generic words like "Lecture" or "Class")
- date: string (YYYY-MM-DD) OR use calendar_week: number when only week present
- calendar_week: number (optional, when exact date missing)
- start_time: string (HH:MM, 24h, optional)
- end_time: string (HH:MM, 24h, optional)
- location: string (optional)
- type: string (lecture|assignment|exam|project|event)
- recurrence: object (optional) with keys freq ("weekly"|"monthly"|"daily"), count (number, optional), until (YYYYMMDD, optional)
- priority: number 1-9 (optional)
- description: full notes/context (readings, deliverables, instructions, room notes)

Rules:
- Title must summarize the specific topic (e.g., "Lecture 5 - Neural Networks: Backprop"), not just "Lecture" or "Class".
- Notes/description should keep all relevant details (what to submit, readings, room, due time) in plain text.
- Assume year {self.current_year} when missing.
- Skip items without any date/week.
- Normalize types (test→exam, homework→assignment).
- Output ONLY the JSON array. No prose, no code fences, no markdown.

Examples of good titles:
- Assignment: "Assignment 1 - Data Cleaning (due 23:59)"
- Exam: "Midterm - Probability and Markov Chains"
- Lecture: "Lecture 7 - Regression Diagnostics"
- Group work: "Team workshop - Prototype demo and feedback"
"""

        # If no AI model is configured, fall back immediately
        if not self.model:
            if config.DEBUG:
                print("No AI model configured, using heuristic extraction")
            self.source = "Local Heuristic (Offline)"
            self.processing_mode = "heuristic"
            self.fallback_reason = self.fallback_reason or "no_model_configured"
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
                    self.processing_mode = "ai"
                    self.fallback_reason = None
                    return copy.deepcopy(cached_events)
                else:
                    # Expired
                    self._ai_cache.pop(cache_key, None)
        except Exception:
            # Cache failures should not block parsing
            cache_key = None

        try:
            full_prompt = f"{system_prompt}\n\n{prompt}\n\nDOCKET CONTENT:\n{text_content}"
            generation_config = {
                "max_output_tokens": 768,
                "temperature": 0.2,
            }

            self.last_prompt = full_prompt
            if config.DEBUG:
                print(f"Calling AI model '{self.source}' with generation_config={generation_config} (API key present: {bool(self.api_key)})")

            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            response_text = response.text.strip()
            self.last_raw_response = response_text

            if config.DEBUG:
                print(f"AI raw response: {response_text}")

            if not response_text:
                if config.DEBUG:
                    print("AI returned empty output; falling back to heuristic")
                self.processing_mode = "heuristic"
                self.fallback_reason = "empty_output"
                return self.heuristic_extraction(text_content)

            events, parse_label = self._try_parse_json(response_text)
            if events is None:
                if config.DEBUG:
                    print(f"JSON Decode Error/repair failed ({parse_label}); falling back to heuristic")
                self.source = "Local Heuristic (Fallback: JSON Parse Error)"
                self.processing_mode = "heuristic"
                self.fallback_reason = "json_parse_error"
                return self.heuristic_extraction(text_content)

            if not isinstance(events, list):
                self.source = "Local Heuristic (Fallback: Invalid JSON structure)"
                self.processing_mode = "heuristic"
                self.fallback_reason = "invalid_json_structure"
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

                normalized_events.append(self._clean_event_fields(normalized_event))

                confidence, low_fields = self._evaluate_confidence(normalized_events[-1], "ai")
                normalized_events[-1]["confidence"] = confidence
                normalized_events[-1]["low_confidence_fields"] = low_fields

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

            self.processing_mode = "ai"
            self.fallback_reason = None

            return normalized_events

        except Exception as e:
            if config.DEBUG:
                print(f"AI Extraction failed: {e}")
                print("Falling back to HEURISTIC OFFLINE EXTRACTION")
            self.source = f"Local Heuristic (Fallback: AI Error - {str(e)})"
            self.processing_mode = "heuristic"
            self.fallback_reason = f"api_failure: {str(e)}"
            return self.heuristic_extraction(text_content)
        
    def heuristic_extraction(self, text: str) -> list:
        """Offline heuristic extraction using regex and keyword matching."""
        self.processing_mode = "heuristic"
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

                description_lines = [line]
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    if next_line and not any(p.search(next_line) for p in [date_pattern, euro_pattern, iso_pattern, week_pattern]):
                        description_lines.append(next_line)

                event = {
                    "module": module_name,
                    "title": title[:100],
                    "date": found_date,
                    "start_time": start_time,
                    "location": location,
                    "type": event_type,
                    "description": " ".join(description_lines)
                }

                cleaned = self._clean_event_fields(event)
                confidence, low_fields = self._evaluate_confidence(cleaned, "heuristic")
                cleaned["confidence"] = confidence
                cleaned["low_confidence_fields"] = low_fields
                events.append(cleaned)

        return events

