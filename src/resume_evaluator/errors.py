"""Exceptions with messages that are safe to show directly to the user."""


class ResumeEvaluatorError(Exception):
    """Base class for all expected, user-facing errors."""


class UnsupportedFormatError(ResumeEvaluatorError):
    """The resume is not a .pdf or .docx file."""


class NoReadableTextError(ResumeEvaluatorError):
    """No (or too little) text could be extracted, e.g. a scanned PDF."""


class ParseError(ResumeEvaluatorError):
    """The file is corrupt, encrypted, or otherwise cannot be read."""


class LLMOutputError(ResumeEvaluatorError):
    """The model did not return valid output after all retries."""
