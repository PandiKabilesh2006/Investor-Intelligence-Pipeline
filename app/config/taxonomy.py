CORE_SECTORS = [
    "Artificial Intelligence",
    "B2B",
    "SaaS",
    "Voice AI",
]

INVESTMENT_STAGES = [
    "Pre-Seed",
    "Seed",
    "Series A",
    "Series B",
    "Growth Stage",
]

INVESTOR_MARKETS = [
    "Global",
    "United States",
    "Canada",
    "United Kingdom",
    "Europe",
    "India",
    "Southeast Asia",
    "Singapore",
    "Middle East",
    "Israel",
    "Latin America",
    "Africa",
    "Australia",
]

INVESTMENT_THEMES = [
    "AI infrastructure",
    "Enterprise Software",
    "Developer Tools",
    "Workflow Automation",
    "Vertical AI",
    "Voice Agents",
    "Machine Learning",
    "Automation",
]

INVESTOR_SEARCH_TERMS = [
    "venture capital firms",
    "VC funds",
    "venture capital",
    "early-stage investors",
    "seed investors",
    "Series A investors",
    "technology investors",
    "venture fund portfolio",
    "VC firm team portfolio",
    "investment thesis venture fund",
]

SECTOR_NORMALIZATION_MAP = {
    "ai": ["Artificial Intelligence"],
    "generative ai": ["Artificial Intelligence"],
    "machine learning": ["Artificial Intelligence"],
    "ai infrastructure": ["Artificial Intelligence"],
    "enterprise ai": ["Artificial Intelligence"],
    "b2b": ["B2B"],
    "business to business": ["B2B"],
    "b2b software": ["B2B"],
    "enterprise software": ["B2B"],
    "workflow automation": ["B2B"],
    "saas": ["SaaS"],
    "software as a service": ["SaaS"],
    "cloud software": ["SaaS"],
    "vertical saas": ["SaaS"],
    "b2b saas": ["B2B SaaS"],
    "conversational ai": ["Voice AI"],
    "speech ai": ["Voice AI"],
    "voice agents": ["Voice AI"],
}

SECTOR_FILTER_EXPANSIONS = {
    "artificial intelligence": ["Artificial Intelligence"],
    "ai": ["Artificial Intelligence"],
    "b2b": ["B2B", "B2B SaaS"],
    "saas": ["SaaS", "B2B SaaS"],
    "b2b saas": ["B2B SaaS", "B2B", "SaaS"],
    "voice ai": ["Voice AI"],
}

STAGE_NORMALIZATION_MAP = {
    "pre seed": "Pre-Seed",
    "pre-seed": "Pre-Seed",
    "preseed": "Pre-Seed",
    "early stage": "Seed",
    "early-stage": "Seed",
    "seed stage": "Seed",
    "seed-stage": "Seed",
    "seed": "Seed",
    "series a": "Series A",
    "series-a": "Series A",
    "series b": "Series B",
    "series-b": "Series B",
    "growth": "Growth Stage",
    "growth equity": "Growth Stage",
    "growth stage": "Growth Stage",
    "expansion": "Growth Stage",
    "expansion stage": "Growth Stage",
}

QUERY_EXPANSIONS = {
    "Artificial Intelligence": [
        "Generative AI",
        "Machine Learning",
        "Foundation Models",
        "AI Infrastructure",
        "Enterprise AI",
        "Autonomous Systems",
    ],
    "Voice AI": [
        "Conversational AI",
        "Speech AI",
        "Speech Infrastructure",
        "Voice Automation",
        "AI Communication",
        "Multimodal AI",
    ],
    "B2B": [
        "Enterprise Software",
        "Business Platforms",
        "Workflow Automation",
        "Enterprise Infrastructure",
    ],
    "SaaS": [
        "Cloud Software",
        "Enterprise SaaS",
        "Subscription Software",
        "Vertical SaaS",
        "Developer Platforms",
    ],
}

FIRECRAWL_IMPORTANT_SUBPAGES = [
    "",
    "/team",
    "/our-team",
    "/investment-team",
    "/people",
    "/partners",
    "/team/partners",
    "/investors",
    "/about",
    "/leadership",
    "/portfolio",
    "/companies",
    "/contact",
]

SEARCH_EXCLUDED_DOMAINS = [
    "bloomberg.com",
    "businessinsider.com",
    "cnbc.com",
    "economictimes.indiatimes.com",
    "facebook.com",
    "forbes.com",
    "fortune.com",
    "instagram.com",
    "medium.com",
    "moneycontrol.com",
    "nytimes.com",
    "pinterest.com",
    "reddit.com",
    "reuters.com",
    "substack.com",
    "tiktok.com",
    "wikipedia.org",
    "wsj.com",
    "youtube.com",
]


def taxonomy_options():
    return {
        "sectors": CORE_SECTORS,
        "stages": INVESTMENT_STAGES,
        "geographies": INVESTOR_MARKETS,
        "themes": INVESTMENT_THEMES,
    }
