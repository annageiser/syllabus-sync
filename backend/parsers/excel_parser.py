"""
Excel file parser for extracting events from .xlsx and .xls files.

Uses pandas and openpyxl to read Excel files and extract text content,
then uses AI via BaseParser to extract event information.
"""

import pandas as pd
import os
from parsers.base_parser import BaseParser


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
            # Read all sheets from Excel file
            excel_file = pd.ExcelFile(file_path)
            
            # Extract text from all sheets
            text_parts = []
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Add sheet name as context
                text_parts.append(f"\\n=== Sheet: {sheet_name} ===\\n")
                
                # Convert DataFrame to readable text
                # Include column headers and all rows
                text_parts.append(df.to_string(index=False, na_rep=''))
                text_parts.append("\\n")
            
            combined_text = "\\n".join(text_parts)
            
            if not combined_text.strip():
                print("WARNING: Excel file appears to be empty")
                return []
            
            # Use AI extraction from base parser
            events = self.extract_events_with_ai(combined_text)
            
            return events
            
        except Exception as e:
            print(f"ERROR: Failed to parse Excel file: {e}")
            if hasattr(self, 'config') and self.config.DEBUG:
                import traceback
                traceback.print_exc()
            raise
