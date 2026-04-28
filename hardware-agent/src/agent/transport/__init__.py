"""Transport abstractions for sending scan results to the backend."""

from .client import BackendClient, BackendSubmissionError, SubmissionResult

__all__ = ["BackendClient", "BackendSubmissionError", "SubmissionResult"]
