"""
Session-level circuit breaker for Groq 70B.

After repeated rate-limit fallbacks, skip 70B for the rest of the process run.
"""

GROQ_70B_RATE_LIMIT_THRESHOLD = 3

RECOVERABLE_GROQ_ERRORS = [
    "rate limit",
    "429",
    "too many requests",
    "rate_limit_exceeded",
    "tokens per minute",
    "requests per minute",
    "request too large",
    "model_decommissioned",
    "service unavailable",
    "overloaded",
    "internal server error",
]

_groq_70b_rate_limit_failures = 0
_skip_groq_70b = False


def is_recoverable_groq_error(error_message: str) -> bool:
    msg = error_message.lower()
    return any(err in msg for err in RECOVERABLE_GROQ_ERRORS)


def should_use_groq_70b() -> bool:
    return not _skip_groq_70b


def record_groq_70b_rate_limit_failure() -> None:
    global _groq_70b_rate_limit_failures, _skip_groq_70b

    _groq_70b_rate_limit_failures += 1

    if _skip_groq_70b:
        return

    if _groq_70b_rate_limit_failures >= GROQ_70B_RATE_LIMIT_THRESHOLD:
        _skip_groq_70b = True
        print(
            f"Groq 70B disabled for remainder of this run "
            f"after {_groq_70b_rate_limit_failures} rate-limit fallbacks. "
            f"Subsequent requests will use 8B directly."
        )


def reset_groq_70b_circuit() -> None:
    global _groq_70b_rate_limit_failures, _skip_groq_70b

    _groq_70b_rate_limit_failures = 0
    _skip_groq_70b = False
