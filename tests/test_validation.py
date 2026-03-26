"""Test input validation for API endpoints."""

import pytest
from pydantic import ValidationError

from backend.routers.repos import IngestRequest, ChatRequest


def test_ingest_request_validates_https_url():
    """Test that valid HTTPS URLs are accepted."""
    request = IngestRequest(url="https://github.com/expressjs/express.git")
    assert request.url == "https://github.com/expressjs/express.git"


def test_ingest_request_validates_ssh_url():
    """Test that valid SSH URLs are accepted."""
    request = IngestRequest(url="git@github.com:owner/repo.git")
    assert request.url == "git@github.com:owner/repo.git"


def test_ingest_request_rejects_command_injection():
    """Test that URLs with command injection attempts are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(url="https://github.com/test/test; rm -rf /")

    assert "Invalid characters" in str(exc_info.value)


def test_ingest_request_rejects_localhost():
    """Test that localhost URLs are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(url="https://localhost/test/repo")

    assert "local/private networks" in str(exc_info.value)


def test_ingest_request_rejects_file_paths():
    """Test that local file paths are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(url="file:///tmp/repo")

    assert "Local file paths" in str(exc_info.value)


def test_chat_request_validates_question():
    """Test that valid questions are accepted."""
    request = ChatRequest(question="How does auth work?")
    assert request.question == "How does auth work?"


def test_chat_request_strips_whitespace():
    """Test that whitespace is stripped from questions."""
    request = ChatRequest(question="  How does auth work?  ")
    assert request.question == "How does auth work?"


def test_chat_request_rejects_empty_question():
    """Test that empty questions are rejected."""
    with pytest.raises(ValidationError):
        ChatRequest(question="   ")


def test_chat_request_validates_history_structure():
    """Test that valid history is accepted."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    request = ChatRequest(question="Follow up question", history=history)
    assert len(request.history) == 2


def test_chat_request_rejects_invalid_history_role():
    """Test that invalid roles in history are rejected."""
    history = [{"role": "system", "content": "Invalid role"}]
    with pytest.raises(ValidationError):
        ChatRequest(question="Test", history=history)


def test_chat_request_rejects_too_long_history():
    """Test that history longer than 50 messages is rejected."""
    history = [{"role": "user", "content": f"Message {i}"} for i in range(51)]
    with pytest.raises(ValidationError):
        ChatRequest(question="Test", history=history)
