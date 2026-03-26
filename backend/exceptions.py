"""
Custom exceptions for Falcon backend.

All exceptions inherit from FalconError, which supports both internal error messages
(logged) and user-safe messages (returned to API clients).
"""


class FalconError(Exception):
    """
    Base exception for all Falcon errors.

    Attributes:
        message: Internal error message (logged server-side)
        user_message: Safe message returned to clients
    """

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or "An internal error occurred. Please try again."


class DatabaseError(FalconError):
    """Database connection or query failures."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(
            message,
            user_message or "Database error occurred. Please try again.",
        )


class IngestionError(FalconError):
    """Repository ingestion failures (git clone, file reading, etc.)."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(
            message,
            user_message or "Failed to ingest repository. Please check the URL and try again.",
        )


class AgentError(FalconError):
    """Agent execution failures (OpenAI API, tool execution, etc.)."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(
            message,
            user_message or "Agent execution error. Please try your question again.",
        )


class ValidationError(FalconError):
    """Input validation failures."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(
            message,
            user_message or "Invalid input. Please check your request and try again.",
        )


class AuthenticationError(FalconError):
    """Authentication failures."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(
            message,
            user_message or "Authentication failed. Please check your API key.",
        )
