"""
HTML file parser for extracting events from .html and .htm files.

Uses BeautifulSoup to parse HTML and extract visible text content,
then uses AI via BaseParser to extract event information.
"""

from bs4 import BeautifulSoup
import os
from backend.parsers.base_parser import BaseParser


class HTMLParser(BaseParser):
    """
    Parser for HTML files (.html, .htm).
    
    Extracts visible text from HTML, removing scripts, styles, and navigation,
    then uses AI to identify events, dates, and module information.
    """
    
    def parse(self, file_path: str) -> list:
        """
        Parse an HTML file and extract events.
        
        Args:
            file_path: Path to the HTML file (.html or .htm)
            
        Returns:
            List of event dictionaries with module, title, date, type, description
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            Exception: If parsing fails
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"HTML file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Extract text
            text = soup.get_text(separator='\\n')
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            text_parts = [line for line in lines if line]
            
            combined_text = "\\n".join(text_parts)
            
            if not combined_text.strip():
                print("WARNING: HTML file appears to have no readable text")
                return []
            
            # Use AI extraction from base parser
            events = self.extract_events_with_ai(combined_text)
            
            return events
            
        except Exception as e:
            print(f"ERROR: Failed to parse HTML file: {e}")
            if hasattr(self, 'config') and self.config.DEBUG:
                import traceback
                traceback.print_exc()
            raise
