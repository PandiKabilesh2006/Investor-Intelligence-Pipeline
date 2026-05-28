from app.utils.normalization import normalize_firm_key


seen_firms = set()


def is_duplicate_firm(firm_name):

    if not firm_name:
        return True

    normalized = normalize_firm_key(firm_name)

    if normalized in seen_firms:
        return True

    seen_firms.add(normalized)

    return False
