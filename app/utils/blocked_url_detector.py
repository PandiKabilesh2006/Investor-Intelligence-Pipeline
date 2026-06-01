from app.config.extraction_policy import (
    BLOCKED_ERROR_PATTERNS,
    BLOCKED_HTTP_STATUS_CODES,
)


class BlockedUrlError(Exception):
    pass


def _combined_text(*values):
    return " ".join(str(value or "") for value in values).lower()


def looks_blocked(status_code=None, text="", error_message=""):
    haystack = _combined_text(text, error_message)

    if status_code in BLOCKED_HTTP_STATUS_CODES:
        return True

    return any(pattern in haystack for pattern in BLOCKED_ERROR_PATTERNS)


def raise_if_blocked(url, status_code=None, text="", error_message=""):
    if looks_blocked(
        status_code=status_code,
        text=text,
        error_message=error_message,
    ):
        detail = error_message or f"Blocked automated extraction for {url}"
        raise BlockedUrlError(detail)
