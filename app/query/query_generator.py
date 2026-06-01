import re

from app.config.ingestion_universe import generate_ingestion_queries
from app.utils.normalization import map_to_search_geography


def _clean(value):
    if value is None:
        return None

    value = str(value).strip()
    return value or None


def _dedupe(queries):
    seen = set()
    cleaned = []

    for query in queries:
        query = " ".join(str(query).split())
        key = query.lower()

        if query and key not in seen:
            seen.add(key)
            cleaned.append(query)

    return cleaned


def _without_global(query):
    return (
        str(query)
        .replace(" in Global", "")
        .replace(" Global ", " ")
        .replace(" Global", "")
    )


def _merge_subject_parts(*parts):
    subject_parts = []
    seen = set()

    for part in parts:
        part = _clean(part)

        if not part:
            continue

        key = part.lower()

        if key in seen:
            continue

        if any(key in existing or existing in key for existing in seen):
            continue

        seen.add(key)
        subject_parts.append(part)

    return " ".join(subject_parts)


def _clean_query_phrase(query):
    query = _without_global(query)
    query = re.sub(r"\bSeed\s+seed investors\b", "Seed investors", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query)
    return query.strip()


def _with_geography(base, geography):
    geography = map_to_search_geography(_clean(geography))

    if geography and geography != "Global":
        return f"{base} in {geography}"

    return base


def _query_subject_aliases(subject):
    subject_lower = (subject or "").lower()
    aliases = [subject]

    if "voice ai" in subject_lower or "voice agent" in subject_lower:
        aliases.extend(
            [
                "voice AI",
                "voice agents",
                "conversational AI",
                "speech AI",
                "AI voice agents",
            ]
        )

    if "artificial intelligence" in subject_lower:
        aliases.extend(
            [
                "AI",
                "generative AI",
                "AI infrastructure",
            ]
        )

    return _dedupe(aliases)


def expand_search_query_variants(query, limit=8):
    query = " ".join(str(query or "").split())

    if not query:
        return []

    base = _without_global(query)
    geography = None
    geography_match = re.search(r"\bin\s+([A-Za-z][A-Za-z\s.\-]+)$", base)

    if geography_match:
        mapped_geography = map_to_search_geography(geography_match.group(1).strip())

        if mapped_geography and mapped_geography != "Global":
            geography = mapped_geography
            base = base[:geography_match.start()].strip()

    variants = []
    query_lower = base.lower()

    if any(signal in query_lower for signal in [" portfolio", " team", " thesis", " vc firm", " venture fund"]):
        variants.append(base)

    stage = ""

    for stage_name in ["Pre-Seed", "Seed", "Series A", "Series B", "Growth Stage"]:
        if stage_name.lower() in query_lower:
            stage = stage_name
            break

    if "voice" in query_lower:
        aliases = _query_subject_aliases("Voice AI")
    elif "artificial intelligence" in query_lower or " ai " in f" {query_lower} ":
        aliases = _query_subject_aliases("Artificial Intelligence")
    else:
        aliases = [base]

    stage_phrase = f" {stage}" if stage else ""

    for alias in aliases:
        variants.extend(
            [
                _with_geography(f"{alias}{stage_phrase} venture capital firm portfolio", geography),
                _with_geography(f"{alias}{stage_phrase} VC firm team portfolio", geography),
                _with_geography(f"{alias}{stage_phrase} venture fund partners portfolio", geography),
                _with_geography(f"{alias}{stage_phrase} early stage fund investment thesis", geography),
                _with_geography(f"{alias} venture capital firm investment team", geography),
                _with_geography(f"{alias} venture fund portfolio companies", geography),
                f"site:signal.nfx.com/investor-lists {alias} VC investors",
                f"site:openvc.app/investor-lists {alias} VC investors",
            ]
        )

    return _dedupe(_clean_query_phrase(item) for item in variants)[:limit]


def _matches(query, values):
    query_lower = query.lower()
    return all(value.lower() in query_lower for value in values if value)


def generate_queries(
    sector=None,
    stage=None,
    geography=None,
    theme=None,
):
    """
    Generate focused investor-discovery queries from explicit search intent.
    """

    sector = _clean(sector)
    stage = _clean(stage)
    geography = map_to_search_geography(_clean(geography))
    theme = _clean(theme)

    queries = []

    if not any([sector, stage, geography, theme]):
        return queries

    subject = _merge_subject_parts(sector, theme) or sector or theme or "startup"
    stage_phrase = f" {stage}" if stage else ""
    geography_phrase = f" in {geography}" if geography and geography != "Global" else ""

    queries.extend(
        [
            _with_geography(f"{subject}{stage_phrase} venture capital firm portfolio", geography),
            _with_geography(f"{subject}{stage_phrase} VC firm team portfolio", geography),
            _with_geography(f"{subject}{stage_phrase} venture fund partners portfolio", geography),
            _with_geography(f"{subject}{stage_phrase} early stage fund investment thesis", geography),
            _with_geography(f"{subject}{stage_phrase} startup investor portfolio partners", geography),
            _with_geography(f"{subject}{stage_phrase} venture capital firm investment team", geography),
            _with_geography(f"{subject}{stage_phrase} VC fund focus sectors portfolio", geography),
        ]
    )

    if not geography_phrase:
        queries.extend(expand_search_query_variants(f"{subject}{stage_phrase} investors"))

    if theme:
        queries.extend(
            [
                _with_geography(f"{theme} venture capital firm portfolio", geography),
                _with_geography(f"{theme} VC fund investment thesis", geography),
                _with_geography(f"{subject} venture fund partners", geography),
                _with_geography(f"{subject} investor portfolio partners", geography),
            ]
        )

    filters = [value for value in [sector, stage, geography, theme] if value]
    curated_matches = [
        query
        for query in generate_ingestion_queries()
        if _matches(query, filters[:3]) or _matches(query, [sector, stage, geography])
    ]

    queries.extend(curated_matches[:10])

    return _dedupe(queries)
