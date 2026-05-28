from app.config.taxonomy import QUERY_EXPANSIONS


def expand_query_theme(theme):
    expansions = [theme]
    expansions.extend(QUERY_EXPANSIONS.get(theme, []))
    return sorted(set(expansions))
