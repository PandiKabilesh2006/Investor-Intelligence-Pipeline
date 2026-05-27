def normalize_investment_stages(stages):

    mapping = {
        "preseed": "Pre-Seed",
        "pre-seed": "Pre-Seed",
        "seed": "Seed",
        "series a": "Series A",
        "series b": "Series B",
        "series c": "Series C",
        "growth": "Growth Stage",
        "ipo": "IPO Stage"
    }

    normalized = []

    for stage in stages:

        cleaned = stage.lower().strip()

        if cleaned in mapping:

            normalized.append(mapping[cleaned])

        else:

            normalized.append(stage)

    return list(set(normalized))


def normalize_sectors(sectors):
    mapping = {
        "ai": ["Artificial Intelligence"],
        "artificial intelligence": ["Artificial Intelligence"],
        "enterprise ai": ["Artificial Intelligence"],
        "voice ai": ["Voice AI"],
        "b2b saas": ["B2B", "SaaS"],
        "b2b": ["B2B"],
        "saas": ["SaaS"]
    }

    normalized = []

    for sector in sectors:
        cleaned = sector.lower().strip()

        if cleaned in mapping:
            normalized.extend(mapping[cleaned])
        else:
            # Fallback logic for arbitrary strings
            if "voice" in cleaned:
                normalized.append("Voice AI")
            elif "ai" in cleaned:
                normalized.append("Artificial Intelligence")
            elif "saas" in cleaned:
                normalized.append("SaaS")
            elif "b2b" in cleaned:
                normalized.append("B2B")

    return list(set(normalized))