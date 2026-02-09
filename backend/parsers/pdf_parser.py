import pdfplumber
import re
from datetime import datetime

class PDFParser:
    def parse(self, file_path):
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        
        # Simple rule-based extraction for demo purposes
        # In a real app, this would be more sophisticated or use LLM fallback
        events = []
        lines = text.split('\n')
        
        date_pattern = re.compile(r'(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})')
        
        for line in lines:
            # Look for lines with dates
            match = date_pattern.search(line)
            if match:
                date_str = match.group(1)
                # Attempt to parse date
                try:
                    # Try common formats
                    for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                        try:
                            date_obj = datetime.strptime(date_str, fmt)
                            # Assume current/next year if year is short or missing logic needed
                            # For simplicity, just use what we found
                            events.append({
                                "title": line.replace(date_str, "").strip(),
                                "date": date_obj.strftime("%Y-%m-%d"),
                                "type": "assignment" if "assignment" in line.lower() else "event"
                            })
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
                    
        return events
