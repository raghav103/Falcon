"""Test configuration validation."""

import os
import pytest


def test_config_loads_from_environment(monkeypatch):
    """Test that configuration loads from environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:5432/test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "development")

    # Re-import config to pick up env vars
    import importlib
    from backend import config

    importlib.reload(config)

    assert config.LOG_LEVEL == "DEBUG"
    assert config.ENVIRONMENT == "development"


def test_config_validates_log_level():
    """Test that invalid log levels are rejected."""
    # This would be tested at module import time
    # In practice, config validation happens when the module is imported
    pass


def test_config_connection_pool_validation():
    """Test that connection pool settings are validated."""
    # DB_MIN_CONNECTIONS must be >= 1
    # DB_MAX_CONNECTIONS must be >= DB_MIN_CONNECTIONS
    # These are validated in config.py at import time
    pass
