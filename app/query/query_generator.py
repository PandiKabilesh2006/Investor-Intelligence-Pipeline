from app.config.ingestion_universe import generate_ingestion_queries


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


def _matches(query, values):
    query_lower = query.lower()
    return all(value.lower() in query_lower for value in values if value)


def generate_queries(
    sector=None,
    stage=None,
    geography=None,
    theme=None,
    business_model=None,
):
    """
    Generate focused investor-discovery queries from explicit search intent.
    """

    sector = _clean(sector)
    stage = _clean(stage)
    geography = _clean(geography)
    theme = _clean(theme)
    business_model = _clean(business_model)

    queries = []
    subject_parts = [value for value in [business_model, sector] if value]
    subject = " ".join(subject_parts) or sector or business_model or theme or "startup"
    stage_phrase = f" {stage}" if stage else ""
    geography_phrase = f" in {geography}" if geography else ""

    queries.extend(
        [
            f"{subject}{stage_phrase} investors{geography_phrase}",
            f"{subject}{stage_phrase} venture capital firms{geography_phrase}",
            f"{subject}{stage_phrase} VC firms{geography_phrase}",
            f"{subject}{stage_phrase} startup investors{geography_phrase}",
            f"top {subject}{stage_phrase} investors{geography_phrase}",
        ]
    )

    if sector and business_model:
        queries.extend(
            [
                f"{sector} {business_model} investors{geography_phrase}",
                f"{business_model} {sector} venture capital{geography_phrase}",
            ]
        )

    if theme:
        queries.extend(
            [
                f"{theme} investors{geography_phrase}",
                f"{theme} venture capital firms{geography_phrase}",
                f"{subject} {theme} investors{geography_phrase}",
            ]
        )

    filters = [value for value in [sector, stage, geography, theme, business_model] if value]
    curated_matches = [
        query
        for query in generate_ingestion_queries()
        if _matches(query, filters[:3]) or _matches(query, [sector, stage, geography])
    ]

    queries.extend(curated_matches[:10])

    return _dedupe(queries)
