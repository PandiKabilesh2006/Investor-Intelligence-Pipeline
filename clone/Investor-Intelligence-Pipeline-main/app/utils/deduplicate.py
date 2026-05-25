seen_firms = set()


def is_duplicate_firm(firm_name):

    if not firm_name:
        return True

    normalized = (
        firm_name
        .lower()
        .replace("ventures", "")
        .replace("capital", "")
        .replace("partners", "")
        .strip()
    )

    if normalized in seen_firms:
        return True

    seen_firms.add(normalized)

    return False