"""
Configuration — reads and validates environment variables with production-ready defaults.

All configuration is loaded at module import time. The application will exit
with a clear error message if required values are missing or invalid.
"""

import os
import sys

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


def _get_required_env(key: str) -> str:
    """
    Get required environment variable or exit with clear error.

    Args:
        key: Environment variable name

    Returns:
        Environment variable value

    Exits:
        If the environment variable is not set
    """
    value = os.getenv(key)
    if not value:
        print(f"ERROR: Required environment variable '{key}' is not set", file=sys.stderr)
        print(f"Please set {key} in your .env file or environment.", file=sys.stderr)
        print("See .env.example for configuration template.", file=sys.stderr)
        sys.exit(1)
    return value


def _get_optional_env(key: str, default: str) -> str:
    """
    Get optional environment variable with default value.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


def _parse_int(value: str, key: str) -> int:
    """
    Parse integer from environment variable with error handling.

    Args:
        value: String value to parse
        key: Environment variable name (for error messages)

    Returns:
        Parsed integer value

    Exits:
        If value cannot be parsed as integer
    """
    try:
        return int(value)
    except ValueError:
        print(f"ERROR: Environment variable '{key}' must be an integer, got: {value}", file=sys.stderr)
        sys.exit(1)


# ==================== REQUIRED CONFIGURATION ====================

# Database configuration
DATABASE_URL = _get_required_env("DATABASE_URL")
USE_SQLITE_FOR_TESTING = _get_optional_env("USE_SQLITE_FOR_TESTING", "false").lower() == "true"


# ==================== OPTIONAL CONFIGURATION ====================

# LLM Configuration - use either OpenAI or Ollama
# For local testing with Ollama (free)
OLLAMA_BASE_URL = _get_optional_env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _get_optional_env("OLLAMA_MODEL", "mistral:7b-instruct")

# For production with OpenAI (paid)
OPENAI_API_KEY = _get_optional_env("OPENAI_API_KEY", "")

# LLM provider selection
LLM_PROVIDER = _get_optional_env("LLM_PROVIDER", "ollama")  # "ollama" or "openai"

# Database connection pool settings
DB_MIN_CONNECTIONS = _parse_int(_get_optional_env("DB_MIN_CONNECTIONS", "2"), "DB_MIN_CONNECTIONS")
DB_MAX_CONNECTIONS = _parse_int(_get_optional_env("DB_MAX_CONNECTIONS", "10"), "DB_MAX_CONNECTIONS")

# Ingestion settings
MAX_FILE_SIZE = _parse_int(
    _get_optional_env("MAX_FILE_SIZE", str(500 * 1024)), "MAX_FILE_SIZE"
)

# Logging configuration
LOG_LEVEL = _get_optional_env("LOG_LEVEL", "INFO").upper()
ENVIRONMENT = _get_optional_env("ENVIRONMENT", "development").lower()

# Security settings
API_KEY = _get_optional_env("API_KEY", "")  # Optional for development
CORS_ORIGINS = [
    origin.strip()
    for origin in _get_optional_env("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]


# ==================== VALIDATION ====================

# Validate database connection pool settings
if DB_MIN_CONNECTIONS < 1:
    print("ERROR: DB_MIN_CONNECTIONS must be at least 1", file=sys.stderr)
    sys.exit(1)

if DB_MAX_CONNECTIONS < DB_MIN_CONNECTIONS:
    print(
        f"ERROR: DB_MAX_CONNECTIONS ({DB_MAX_CONNECTIONS}) must be >= DB_MIN_CONNECTIONS ({DB_MIN_CONNECTIONS})",
        file=sys.stderr,
    )
    sys.exit(1)

# Validate file size limit
if MAX_FILE_SIZE < 1024:  # At least 1KB
    print(f"ERROR: MAX_FILE_SIZE must be at least 1024 bytes, got: {MAX_FILE_SIZE}", file=sys.stderr)
    sys.exit(1)

# Validate log level
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if LOG_LEVEL not in VALID_LOG_LEVELS:
    print(
        f"ERROR: LOG_LEVEL must be one of {VALID_LOG_LEVELS}, got: {LOG_LEVEL}",
        file=sys.stderr,
    )
    sys.exit(1)

# Validate environment
VALID_ENVIRONMENTS = ["development", "production"]
if ENVIRONMENT not in VALID_ENVIRONMENTS:
    print(
        f"ERROR: ENVIRONMENT must be one of {VALID_ENVIRONMENTS}, got: {ENVIRONMENT}",
        file=sys.stderr,
    )
    sys.exit(1)

# Validate CORS origins
if not CORS_ORIGINS:
    print("ERROR: CORS_ORIGINS must have at least one origin", file=sys.stderr)
    sys.exit(1)

# Warn if API_KEY not set in production
if ENVIRONMENT == "production" and not API_KEY:
    print("WARNING: API_KEY is not set in production environment!", file=sys.stderr)
    print("Authentication will be disabled. This is a security risk.", file=sys.stderr)

# Validate LLM provider configuration
VALID_LLM_PROVIDERS = ["ollama", "openai"]
if LLM_PROVIDER not in VALID_LLM_PROVIDERS:
    print(
        f"ERROR: LLM_PROVIDER must be one of {VALID_LLM_PROVIDERS}, got: {LLM_PROVIDER}",
        file=sys.stderr,
    )
    sys.exit(1)

# Validate LLM provider requirements
if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY is required when LLM_PROVIDER=openai", file=sys.stderr)
    sys.exit(1)

if LLM_PROVIDER == "ollama":
    print(f"INFO: Using Ollama at {OLLAMA_BASE_URL} with model {OLLAMA_MODEL}", file=sys.stderr)
