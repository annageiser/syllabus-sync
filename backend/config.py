"""
Configuration management for Syllabus-Sync backend.

Uses environment variables for flexible deployment configuration.
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Centralized configuration for the Syllabus-Sync backend."""
    
    # Google AI (Free Tier)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Google Cloud / Vertex AI (Legacy/Optional)
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    VERTEX_AI_MODEL: str = os.getenv("VERTEX_AI_MODEL", "gemini-1.5-flash-001")
    
    # Server Configuration
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000"
    ).split(",")
    
    # Application Settings
    DEFAULT_YEAR: int = int(os.getenv("DEFAULT_YEAR", "2026"))
    TEMP_FILE_CLEANUP: bool = os.getenv("TEMP_FILE_CLEANUP", "true").lower() == "true"
    
    # Debugging
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    @classmethod
    def log_config(cls):
        """Print current configuration (for debugging)."""
        print("=" * 50)
        print("Syllabus-Sync Backend Configuration")
        print("=" * 50)
        print(f"Gemini API Key: {'Set' if cls.GEMINI_API_KEY else 'Not Set'}")
        print(f"Google Cloud Project: {cls.GOOGLE_CLOUD_PROJECT}")
        print(f"Vertex AI Location: {cls.VERTEX_AI_LOCATION}")
        print(f"Vertex AI Model: {cls.VERTEX_AI_MODEL}")
        print(f"Backend Host: {cls.BACKEND_HOST}")
        print(f"Backend Port: {cls.BACKEND_PORT}")
        print(f"CORS Origins: {cls.CORS_ORIGINS}")
        print(f"Default Year: {cls.DEFAULT_YEAR}")
        print(f"Debug Mode: {cls.DEBUG}")
        print("=" * 50)


# Singleton instance
config = Config()
