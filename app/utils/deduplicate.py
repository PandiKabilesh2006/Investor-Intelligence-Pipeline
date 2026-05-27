from app.validation.investor_validation import normalize_firm_key

_seen_firm_keys: set[str] = set()


def reset_firm_dedup_cache() -> None:
    _seen_firm_keys.clear()


def is_duplicate_firm(firm_name: str) -> bool:
    key = normalize_firm_key(firm_name)

    if not key:
        return True

    if key in _seen_firm_keys:
        return True

    _seen_firm_keys.add(key)
    return False
