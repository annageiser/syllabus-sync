"""
PDF parser for extracting events from PDF files.

Uses pdfplumber to extract text from PDF files, then uses AI via BaseParser
to extract event information.
"""

import pdfplumber
import os
from parsers.base_parser import BaseParser


class PDFParser(BaseParser):
    """
    Parser for PDF files.
    
    Extracts text from PDF pages using pdfplumber, then uses AI to identify
    events, dates, module information, and calendar weeks.
    """
    
    def parse(self, file_path: str) -> list:
        """
        Parse a PDF file and extract events using AI.
        
        Args:
            file_path: Path to the PDF file to parse.
            
        Returns:
            List of event dictionaries with keys: module, title, date, type, description.
            
        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            Exception: If parsing fails.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        try:
            # Extract text from PDF
            text_parts = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"\\n--- Page {page_num} ---\\n")
                        text_parts.append(text)
            
            combined_text = "\\n".join(text_parts)
            
            if not combined_text.strip():
                print("WARNING: PDF appears to be empty or contains only images")
                return []
            
            # Use AI extraction from base parser
            events = self.extract_events_with_ai(combined_text)
            
            return events
            
        except Exception as e:
            print(f"ERROR: Failed to parse PDF: {e}")
            from config import config
            if config.DEBUG:
                import traceback
                traceback.print_exc()
            raise
