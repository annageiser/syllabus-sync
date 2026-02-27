import json

def repair_json(text):
    # Check if we are inside a string
    in_string = False
    escape = False
    for char in text:
        if escape:
            escape = False
        elif char == '\\':
            escape = True
        elif char == '"':
            in_string = not in_string
            
    if in_string:
        text += '"'
        
    # Now count brackets outside of strings
    # A simple way is to remove all strings and then count
    import re
    # Remove escaped quotes
    no_escapes = text.replace('\\"', '')
    # Remove strings
    no_strings = re.sub(r'"[^"]*"', '', no_escapes)
    
    opens = no_strings.count("[") - no_strings.count("]")
    brace_opens = no_strings.count("{") - no_strings.count("}")
    
    if brace_opens > 0:
        text += "}" * brace_opens
    if opens > 0:
        text += "]" * opens
        
    return text

truncated = """[
  {
    "module": "BÖK/BIT",
    "title": "Exam Review",
    "description": "Termin und Zeit provisorisch -"""

repaired = rerepaired (truncated)
print(f"Repaired:\n{repaired}")
try:
    print(json.loads(repaired))
exceptexceptexceptexcep    print(f"Error: {e}")
