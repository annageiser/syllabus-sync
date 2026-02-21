"""
Configuration management for Syllabus-Sync backend.

Uses environment variables for flexible deployment configuration.
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _csv_to_list(value: str) -> List[str]:
    """Parse a comma-separated string into a trimmed list."""
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    """Centralized configuration for the Syllabus-Sync backend."""
    
    # Google AI (Free Tier)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Google Cloud / Vertex AI (Advanced/Enterprise)
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    
    # Model configuration (Gemini API or Vertex AI)
    # This identifies WHICH Gemini model to use
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", os.getenv("VERTEX_AI_MODEL", "gemini-1.5-flash"))
    
    # Server Configuration
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = _csv_to_list(
        os.getenv(
            "CORS_ORIGINS", 
            "http://localhost:3000"
        )
    )
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
    CORS_ALLOW_METHODS: List[str] = _csv_to_list(os.getenv("CORS_ALLOW_METHODS", "GET,POST,OPTIONS"))
    CORS_ALLOW_HEADERS: List[str] = _csv_to_list(os.getenv("CORS_ALLOW_HEADERS", "Authorization,Content-Type"))
    
    # Application Settings
    DEFAULT_YEAR: int = int(os.getenv("DEFAULT_YEAR", "2026"))
    TEMP_FILE_CLEANUP: bool = os.getenv("TEMP_FILE_CLEANUP", "true").lower() == "true"
    JOB_TTL_SECONDS: int = int(os.getenv("JOB_TTL_SECONDS", "1800"))
    JOB_SWEEP_INTERVAL_SECONDS: int = int(os.getenv("JOB_SWEEP_INTERVAL_SECONDS", "300"))
    JOB_STORE_MAX_ITEMS: int = int(os.getenv("JOB_STORE_MAX_ITEMS", "500"))
    JOB_MAX_RETRIES: int = int(os.getenv("JOB_MAX_RETRIES", "2"))
    JOB_BACKOFF_BASE_SECONDS: float = float(os.getenv("JOB_BACKOFF_BASE_SECONDS", "3.0"))
    JOB_BACKOFF_JITTER_SECONDS: float = float(os.getenv("JOB_BACKOFF_JITTER_SECONDS", "2.0"))
    DLQ_MAX_ITEMS: int = int(os.getenv("DLQ_MAX_ITEMS", "200"))
    DLQ_TTL_SECONDS: int = int(os.getenv("DLQ_TTL_SECONDS", str(24 * 3600)))
    JOB_WALL_TIMEOUT_SECONDS: int = int(os.getenv("JOB_WALL_TIMEOUT_SECONDS", "60"))
    JOB_CPU_LIMIT_MS: int = int(os.getenv("JOB_CPU_LIMIT_MS", "0"))  # best-effort/doc only
    JOB_MEM_LIMIT_MB: int = int(os.getenv("JOB_MEM_LIMIT_MB", "0"))  # best-effort/doc only
    AI_PARSE_TIMEOUT_SECONDS: int = int(os.getenv("AI_PARSE_TIMEOUT_SECONDS", "30"))
    USE_REDIS_QUEUE: bool = os.getenv("USE_REDIS_QUEUE", "false").lower() == "true"
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_TLS: bool = os.getenv("REDIS_TLS", "false").lower() == "true"
    READINESS_MAX_SWEEPER_LAG_SECONDS: int = int(os.getenv("READINESS_MAX_SWEEPER_LAG_SECONDS", "900"))
    READINESS_QUEUE_CHECK_TIMEOUT_SECONDS: int = int(os.getenv("READINESS_QUEUE_CHECK_TIMEOUT_SECONDS", "3"))
    AI_CACHE_TTL_SECONDS: int = int(os.getenv("AI_CACHE_TTL_SECONDS", "900"))
    AI_CACHE_SWEEP_INTERVAL_SECONDS: int = int(os.getenv("AI_CACHE_SWEEP_INTERVAL_SECONDS", "300"))
    AI_CACHE_MAX_ENTRIES: int = int(os.getenv("AI_CACHE_MAX_ENTRIES", "256"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # json or text
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    METRICS_SINK: str = os.getenv("METRICS_SINK", "inline")  # inline|none
    ENABLE_TRACING: bool = os.getenv("ENABLE_TRACING", "false").lower() == "true"

    # Security and protection toggles
    ENABLE_MAGIC_VALIDATION: bool = os.getenv("ENABLE_MAGIC_VALIDATION", "true").lower() == "true"
    ENABLE_AV_SCAN: bool = os.getenv("ENABLE_AV_SCAN", "false").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    API_TOKEN_REQUIRED: bool = os.getenv("API_TOKEN_REQUIRED", "false").lower() == "true"
    API_TOKENS: List[str] = _csv_to_list(os.getenv("API_TOKENS", ""))
    API_TOKEN_HEADER: str = os.getenv("API_TOKEN_HEADER", "X-API-Key")
    
    # Debugging
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    @classmethod
    def log_config(cls):
        """Print current configuration (for debugging)."""
        print("=" * 50)
        print("Syllabus-Sync Backend Configuration")
        print("=" * 50)
        print(f"Active AI Key: {'Set' if cls.GEMINI_API_KEY else 'Not Set'}")
        print(f"Selected Model: {cls.GEMINI_MODEL}")
        print(f"Cloud Project: {cls.GOOGLE_CLOUD_PROJECT if cls.GOOGLE_CLOUD_PROJECT else 'N/A'}")
        print(f"Location: {cls.VERTEX_AI_LOCATION}")
        print(f"Backend Host: {cls.BACKEND_HOST}")
        print(f"Backend Port: {cls.BACKEND_PORT}")
        print(f"CORS Origins: {cls.CORS_ORIGINS}")
        print(f"CORS Allow Credentials: {cls.CORS_ALLOW_CREDENTIALS}")
        print(f"CORS Allow Methods: {cls.CORS_ALLOW_METHODS}")
        print(f"CORS Allow Headers: {cls.CORS_ALLOW_HEADERS}")
        print(f"Default Year: {cls.DEFAULT_YEAR}")
        print(f"Job TTL (s): {cls.JOB_TTL_SECONDS}")
        print(f"Job Sweep Interval (s): {cls.JOB_SWEEP_INTERVAL_SECONDS}")
        print(f"Job Store Max Items: {cls.JOB_STORE_MAX_ITEMS}")
        print(f"Job Max Retries: {cls.JOB_MAX_RETRIES}")
        print(f"Job Backoff Base (s): {cls.JOB_BACKOFF_BASE_SECONDS}")
        print(f"Job Backoff Jitter (s): {cls.JOB_BACKOFF_JITTER_SECONDS}")
        print(f"DLQ Max Items: {cls.DLQ_MAX_ITEMS}")
        print(f"DLQ TTL (s): {cls.DLQ_TTL_SECONDS}")
        print(f"Job Wall Timeout (s): {cls.JOB_WALL_TIMEOUT_SECONDS}")
        print(f"AI Parse Timeout (s): {cls.AI_PARSE_TIMEOUT_SECONDS}")
        print(f"Redis Queue Enabled: {cls.USE_REDIS_QUEUE}")
        print(f"Redis URL: {cls.REDIS_URL or 'N/A'}")
        print(f"Readiness Max Sweeper Lag (s): {cls.READINESS_MAX_SWEEPER_LAG_SECONDS}")
        print(f"AI Cache TTL (s): {cls.AI_CACHE_TTL_SECONDS}")
        print(f"AI Cache Sweep Interval (s): {cls.AI_CACHE_SWEEP_INTERVAL_SECONDS}")
        print(f"AI Cache Max Entries: {cls.AI_CACHE_MAX_ENTRIES}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print(f"Log Format: {cls.LOG_FORMAT}")
        print(f"Metrics Enabled: {cls.ENABLE_METRICS} ({cls.METRICS_SINK})")
        print(f"Tracing Enabled: {cls.ENABLE_TRACING}")
        print(f"Magic Validation Enabled: {cls.ENABLE_MAGIC_VALIDATION}")
        print(f"AV Scan Enabled: {cls.ENABLE_AV_SCAN}")
        print(f"Rate Limit: {cls.RATE_LIMIT_REQUESTS}/{cls.RATE_LIMIT_WINDOW_SECONDS}s")
        print(f"API Token Required: {cls.API_TOKEN_REQUIRED}")
        print(f"Debug Mode: {cls.DEBUG}")
        print("=" * 50)


# Singleton instance
config = Config()
