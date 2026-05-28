import re

from app.config.taxonomy import (
    INVESTMENT_STAGES,
    SECTOR_FILTER_EXPANSIONS,
    SECTOR_NORMALIZATION_MAP,
    STAGE_NORMALIZATION_MAP,
)


UNKNOWN_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "not available",
    "not specified",
    "unknown",
}


def normalize_firm_key(firm_name):
    if not firm_name:
        return ""

    normalized = str(firm_name).lower()
    normalized = re.sub(
        r"\((?:formerly|previously|aka|also known as|known as)[^)]+\)",
        "",
        normalized,
    )
    normalized = normalized.replace("&", "and")
    normalized = re.sub(r"\b(the|llc|llp|ltd|limited|inc|incorporated|corp|corporation)\b", "", normalized)
    normalized = re.sub(r"[^a-z0-9]", "", normalized)
    return normalized


def clean_list_values(values):
    cleaned = []
    seen = set()

    for value in values or []:
        if value is None:
            continue

        value = " ".join(str(value).strip().split())
        key = value.lower()

        if key in UNKNOWN_VALUES or key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

    return cleaned


def merge_clean_lists(*lists):
    merged = []

    for values in lists:
        merged.extend(values or [])

    return clean_list_values(merged)


def normalize_geography(values):
    mapping = {
        "u.s.": "United States",
        "u.s": "United States",
        "usa": "United States",
        "us": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "uae": "United Arab Emirates",
    }
    normalized = []

    for value in clean_list_values(values):
        key = value.lower().strip()
        mapped = mapping.get(key, value)
        normalized.append(mapped)

    return clean_list_values(normalized)


EUROPE_COUNTRIES = {
    "albania", "andorra", "austria", "belarus", "belgium", "bosnia and herzegovina",
    "bulgaria", "croatia", "cyprus", "czechia", "czech republic", "denmark", "estonia",
    "finland", "france", "germany", "greece", "hungary", "iceland", "ireland", "italy",
    "kosovo", "latvia", "liechtenstein", "lithuania", "luxembourg", "malta", "moldova",
    "monaco", "montenegro", "netherlands", "north macedonia", "norway", "poland",
    "portugal", "romania", "serbia", "slovakia", "slovenia", "spain", "sweden",
    "switzerland", "ukraine",
}

SOUTHEAST_ASIA_COUNTRIES = {
    "brunei", "cambodia", "indonesia", "laos", "malaysia", "myanmar", "philippines",
    "singapore", "thailand", "timor-leste", "timor leste", "vietnam",
}

MIDDLE_EAST_COUNTRIES = {
    "bahrain", "cyprus", "egypt", "iran", "iraq", "israel", "jordan", "kuwait",
    "lebanon", "oman", "palestine", "qatar", "saudi arabia", "syria", "turkey",
    "united arab emirates", "uae", "yemen",
}

LATIN_AMERICA_COUNTRIES = {
    "argentina", "bolivia", "brazil", "chile", "colombia", "costa rica", "cuba",
    "dominican republic", "ecuador", "el salvador", "guatemala", "honduras", "mexico",
    "nicaragua", "panama", "paraguay", "peru", "uruguay", "venezuela",
}

AFRICA_COUNTRIES = {
    "algeria", "angola", "benin", "botswana", "burkina faso", "burundi", "cameroon",
    "cape verde", "central african republic", "chad", "congo", "democratic republic of the congo",
    "djibouti", "egypt", "eritrea", "ethiopia", "ghana", "kenya", "morocco",
    "mozambique", "namibia", "nigeria", "rwanda", "senegal", "south africa", "tanzania",
    "tunisia", "uganda", "zambia", "zimbabwe",
}

CORE_INVESTOR_MARKETS = {
    "global": "Global",
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "canada": "Canada",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "india": "India",
    "singapore": "Singapore",
    "israel": "Israel",
    "australia": "Australia",
    "new zealand": "Australia",
    "europe": "Europe",
    "southeast asia": "Southeast Asia",
    "middle east": "Middle East",
    "latin america": "Latin America",
    "africa": "Africa",
}


def map_to_search_geography(value):
    if not value:
        return None

    cleaned = " ".join(str(value).strip().split())
    key = cleaned.lower()

    if key in CORE_INVESTOR_MARKETS:
        return CORE_INVESTOR_MARKETS[key]

    if key in EUROPE_COUNTRIES:
        return "Europe"

    if key in SOUTHEAST_ASIA_COUNTRIES:
        return "Southeast Asia"

    if key in MIDDLE_EAST_COUNTRIES:
        return "Middle East"

    if key in LATIN_AMERICA_COUNTRIES:
        return "Latin America"

    if key in AFRICA_COUNTRIES:
        return "Africa"

    return "Global"


def expand_geography_filter(value):
    if not value:
        return []

    mapped = map_to_search_geography(value)
    values = [value]

    if mapped and mapped != value:
        values.append(mapped)

    return clean_list_values(values)


def normalize_stage(values):
    normalized = []

    for value in clean_list_values(values):
        mapped = STAGE_NORMALIZATION_MAP.get(value.lower().strip(), value)

        if mapped in INVESTMENT_STAGES:
            normalized.append(mapped)

    return clean_list_values(normalized)


def normalize_sector(values):
    normalized = []

    for value in clean_list_values(values):
        mapped = SECTOR_NORMALIZATION_MAP.get(value.lower().strip(), [value])
        normalized.extend(mapped)

    return clean_list_values(normalized)


def expand_sector_filter(value):
    if not value:
        return []

    key = str(value).lower().strip()
    return SECTOR_FILTER_EXPANSIONS.get(key, [value])
