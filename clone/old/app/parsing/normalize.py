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
        "ai": "Artificial Intelligence",
        "b2b saas": "B2B SaaS",
        "voice ai": "Voice AI",
        "enterprise ai": "Enterprise AI"
    }

    normalized = []

    for sector in sectors:

        cleaned = sector.lower().strip()

        if cleaned in mapping:

            normalized.append(mapping[cleaned])

        else:

            normalized.append(sector)

    return list(set(normalized))