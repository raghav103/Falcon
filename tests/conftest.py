"""
Pytest fixtures for Falcon tests.

Provides test fixtures for database connections, test clients, and common test data.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    """
    FastAPI test client.

    Usage:
        def test_health(client):
            response = client.get("/health")
            assert response.status_code == 200
    """
    return TestClient(app)


@pytest.fixture
def sample_git_urls():
    """Sample Git repository URLs for testing."""
    return {
        "valid_https": "https://github.com/expressjs/express.git",
        "valid_ssh": "git@github.com:owner/repo.git",
        "invalid_command_injection": "https://github.com/test/test; rm -rf /",
        "invalid_localhost": "https://localhost/test/repo",
        "invalid_file_path": "file:///tmp/repo",
    }
