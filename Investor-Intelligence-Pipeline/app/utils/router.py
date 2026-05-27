import re
from typing import Tuple, Optional

# Keywords associated with each preset for smart token matching
PRESET_KEYWORDS = {
    "1": {"ai", "ml", "artificial", "intelligence", "machine", "learning", "deeptech", "deep", "neural", "vision", "nlp", "llm", "cognitive"},
    "2": {"saas", "software", "enterprise", "b2b", "workflow", "cloud", "productivity", "crm", "erp", "sme"},
    "3": {"devtools", "developer", "infrastructure", "devops", "cloud", "infra", "apis", "database", "kubernetes", "git"},
    "4": {"voice", "speech", "conversational", "audio", "chatbots", "speech-to-text", "tts", "call", "assistant"},
    "5": {"fintech", "finance", "payment", "banking", "lending", "insurance", "insurtech", "wealthtech", "crypto", "blockchain", "billing"},
    "6": {"healthtech", "health", "biotech", "medical", "clinical", "pharma", "healthcare", "wellness", "therapeutics"},
    "7": {"climate", "sustainability", "energy", "clean", "cleantech", "carbon", "green", "renewable", "solar", "wind", "esg"}
}

COMMON_GEOGRAPHIES = {
    "india", "chennai", "mumbai", "bangalore", "bengaluru", "delhi", "noida", "gurgaon", "hyderabad", "pune",
    "us", "usa", "america", "california", "silicon valley", "new york", "boston", "san francisco",
    "europe", "uk", "london", "germany", "berlin", "france", "paris",
    "southeast asia", "singapore", "indonesia", "vietnam", "malaysia", "philippines"
}

def route_query_to_preset(user_input: str) -> Tuple[str, str, str]:
    """
    Route a raw user text query (e.g. "AI deeptech seed funds in india")
    to the most relevant preset choice, and extract the geography filter if present.
    
    Returns:
        Tuple[str, str, str]: (preset_choice, geography, matched_preset_name)
    """
    user_input_lower = user_input.strip().lower()
    
    # 1. Try to extract geography
    geography = ""
    
    # Look for "in <location>" or "at <location>"
    geo_match = re.search(r"\b(in|at|for|focused on)\s+([a-zA-Z\s]+)", user_input_lower)
    if geo_match:
        potential_geo = geo_match.group(2).strip()
        # Cap at 3 words to avoid eating the whole string
        potential_geo_words = potential_geo.split()[:3]
        geography = " ".join(potential_geo_words).title()
        
        # Clean geography of common trailing words like "investors", "vcs"
        for word in ["investors", "vcs", "funds", "firms", "companies"]:
            geography = re.sub(rf"\b{word}\b", "", geography, flags=re.IGNORECASE).strip()
            
    # If no "in <location>" found, scan directly for known geographic terms
    if not geography:
        for geo in COMMON_GEOGRAPHIES:
            if re.search(rf"\b{geo}\b", user_input_lower):
                geography = geo.title()
                if geography == "Usa":
                    geography = "US"
                break

    # 2. Tokenize and clean query to score it against presets
    # Remove common filler words
    clean_input = user_input_lower
    if geography:
        clean_input = clean_input.replace(geography.lower(), "")
    
    filler_words = {
        "in", "at", "for", "focused", "on", "investors", "vcs", "funds", "firms", "seed", "early", "stage",
        "venture", "capital", "partners", "team", "portfolio", "companies", "startup", "startups",
        "find", "me", "some", "active", "list", "show", "get"
    }
    
    tokens = set(re.findall(r"\b[a-z]{2,}\b", clean_input)) - filler_words
    
    # 3. Score against preset keywords
    best_choice = "8" # Default to Custom Query
    best_score = 0
    
    for choice, keywords in PRESET_KEYWORDS.items():
        overlap = tokens.intersection(keywords)
        score = len(overlap)
        
        # Give higher weight to direct matches (e.g. "ai" or "saas")
        for token in tokens:
            if token in keywords:
                score += 1
                
        if score > best_score:
            best_score = score
            best_choice = choice

    # Determine matched name
    from run_pipeline import QUERY_PRESETS # Safe import as it is in the path
    preset_name = QUERY_PRESETS.get(best_choice, {}).get("name", "Custom Query")
    
    # If matched preset is Custom (8), we'll pass the cleaned query as the search term
    # so they don't have to re-type it.
    return best_choice, geography, preset_name
