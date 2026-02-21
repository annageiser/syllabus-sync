"""
Excel file parser for extracting events from .xlsx and .xls files.

Uses pandas and openpyxl to read Excel files and extract text content,
then uses AI via BaseParser to extract event information.
"""

import pandas as pd
import os
from backend.parsers.base_parser import BaseParser


class ExcelParser(BaseParser):
    """
    Parser for Excel files (.xlsx, .xls).
    
    Extracts text from all sheets and uses AI to identify events, dates,
    and module information.
    """
    
    def parse(self, file_path: str) -> list:
        """
        Parse an Excel file and extract events.
        
        Args:
            file_path: Path to the Excel file (.xlsx or .xls)
            
        Returns:
            List of event dictionaries with module, title, date, type, description
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            Exception: If parsing fails
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Excel file not found: {file_path}")
        
        try:
            excel_file = pd.ExcelFile(file_path)

            # First try structured extraction if columns look tabular
            structured_events = []
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                structured_events.extend(self._extract_structured(df))

            if structured_events:
                return structured_events

            # Fallback to AI with text flattening
            text_parts = []
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                text_parts.append(f"\n=== Sheet: {sheet_name} ===\n")
                text_parts.append(df.to_string(index=False, na_rep=''))
                text_parts.append("\n")

            combined_text = "\n".join(text_parts)
            if not combined_text.strip():
                print("WARNING: Excel file appears to be empty")
                return []

            return self.extract_events_with_ai(combined_text)

        except Exception as e:
            print(f"ERROR: Failed to parse Excel file: {e}")
            if hasattr(self, 'config') and self.config.DEBUG:
                import traceback
                traceback.print_exc()
            raise

    def _extract_structured(self, df: pd.DataFrame) -> list:
        events = []
        if df.empty:
            return events

        col_map = {c.lower(): c for c in df.columns}
        date_col = next((col_map[c] for c in col_map if any(k in c for k in ["date", "datum", "day"])), None)
        title_col = next((col_map[c] for c in col_map if any(k in c for k in ["title", "event", "topic", "name"])), None)
        time_col = next((col_map[c] for c in col_map if "time" in c or "hour" in c or "start" in c), None)
        end_time_col = next((col_map[c] for c in col_map if "end" in c and "time" in c), None)
        type_col = next((col_map[c] for c in col_map if "type" in c or "category" in c), None)
        location_col = next((col_map[c] for c in col_map if "location" in c or "room" in c or "place" in c), None)

        if not date_col or not title_col:
            return events

        for _, row in df.iterrows():
            raw_date = row.get(date_col)
            if pd.isna(raw_date):
                continue
            try:
                parsed_date = pd.to_datetime(raw_date, errors='coerce')
                if pd.notna(parsed_date) and parsed_date.year < 1900:
                    parsed_date = parsed_date.replace(year=self.current_year)
            except Exception:
                parsed_date = None
            if parsed_date is None or pd.isna(parsed_date):
                continue

            date_str = parsed_date.strftime("%Y-%m-%d")
            start_time = None
            end_time = None

            if time_col and not pd.isna(row.get(time_col)):
                try:
                    start_time = pd.to_datetime(str(row.get(time_col))).strftime("%H:%M")
                except Exception:
                    start_time = None

            if end_time_col and not pd.isna(row.get(end_time_col)):
                try:
                    end_time = pd.to_datetime(str(row.get(end_time_col))).strftime("%H:%M")
                except Exception:
                    end_time = None

            title = str(row.get(title_col) or "").strip()
            if not title:
                continue

            event_type = "lecture"
            if type_col and not pd.isna(row.get(type_col)):
                event_type = str(row.get(type_col)).strip().lower()
            elif any(k in title.lower() for k in ["exam", "test", "quiz"]):
                event_type = "exam"
            elif any(k in title.lower() for k in ["assignment", "homework", "due"]):
                event_type = "assignment"
            elif "project" in title.lower():
                event_type = "project"

            location = None
            if location_col and not pd.isna(row.get(location_col)):
                location = str(row.get(location_col)).strip()

            events.append({
                "module": "",
                "title": title,
                "date": date_str,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "type": event_type,
                "description": "",
            })

        return events
