"""Shared exception types for the pipeline."""


class SautiError(Exception):
    """Base exception for Sauti pipeline errors."""


class AudioProcessingError(SautiError):
    """Raised when audio processing fails."""
