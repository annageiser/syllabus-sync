import sys
import os
sys.path.append(os.path.abspath('.'))
from backend.parsers.base_parser import BaseParser

parser = BaseParser()
print(f"Model: {parser.model}")
print(f"Source: {parser.source}")
print(f"Processing mode: {parser.processing_mode}")
print(f"Fallback reason: {parser.fallback_reason}")

try:
    events = parser.extract_events_with_ai("Lecture 1 on 2026-01-15: Introduction to AI")
    print(f"Events: {events}")
except Exception as e:
    print(f"Error: {e}")
