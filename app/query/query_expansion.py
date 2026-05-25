# =========================================
# QUERY EXPANSION MAP
# =========================================

QUERY_EXPANSIONS = {

    "Artificial Intelligence": [

        "Generative AI",

        "Machine Learning",

        "Foundation Models",

        "AI Infrastructure",

        "Enterprise AI",

        "Autonomous Systems"
    ],

    "Voice AI": [

        "Conversational AI",

        "Speech AI",

        "Speech Infrastructure",

        "Voice Automation",

        "AI Communication",

        "Multimodal AI"
    ],

    "B2B": [

        "Enterprise Software",

        "Business Platforms",

        "Workflow Automation",

        "Enterprise Infrastructure",

        "SaaS Infrastructure"
    ],

    "SaaS": [

        "Cloud Software",

        "Enterprise SaaS",

        "Subscription Software",

        "Vertical SaaS",

        "Developer Platforms"
    ]
}


# =========================================
# EXPAND QUERY THEMES
# =========================================

def expand_query_theme(theme):

    expansions = [

        theme
    ]


    additional = QUERY_EXPANSIONS.get(

        theme,

        []
    )


    expansions.extend(

        additional
    )


    return sorted(

        list(set(expansions))
    )