from rapidfuzz import fuzz
from sentence_transformers import (
    SentenceTransformer
)

from sklearn.metrics.pairwise import (
    cosine_similarity
)

import numpy as np


# =========================================
# EMBEDDING MODEL
# =========================================

embedding_model = SentenceTransformer(

    "all-MiniLM-L6-v2"
)


# =========================================
# THRESHOLDS
# =========================================

FUZZY_THRESHOLD = 88

SEMANTIC_THRESHOLD = 0.82


# =========================================
# NORMALIZATION
# =========================================

def normalize_text(text):

    if not text:

        return ""


    return (

        text.lower()

        .replace("capital", "")

        .replace("ventures", "")

        .replace("venture partners", "")

        .replace("partners", "")

        .replace("vc", "")

        .replace(",", "")

        .replace(".", "")

        .replace("-", " ")

        .strip()
    )


# =========================================
# BUILD ENTITY REPRESENTATION
# =========================================

def build_entity_text(investor):

    components = [

        investor.get("firm", ""),

        investor.get("website", ""),

        " ".join(

            investor.get(
                "focus_sectors",
                []
            )
        ),

        " ".join(

            investor.get(
                "investment_stage",
                []
            )
        )
    ]


    return " ".join(components)


# =========================================
# FUZZY NAME SIMILARITY
# =========================================

def fuzzy_name_similarity(

    investor_a,

    investor_b
):

    name_a = normalize_text(

        investor_a.get("firm", "")
    )

    name_b = normalize_text(

        investor_b.get("firm", "")
    )


    if not name_a or not name_b:

        return 0.0


    return (

        fuzz.ratio(

            name_a,

            name_b
        ) / 100
    )


# =========================================
# SEMANTIC SIMILARITY
# =========================================

def semantic_similarity(

    investor_a,

    investor_b
):

    text_a = build_entity_text(

        investor_a
    )

    text_b = build_entity_text(

        investor_b
    )


    embedding_a = embedding_model.encode(

        text_a
    )

    embedding_b = embedding_model.encode(

        text_b
    )


    similarity = cosine_similarity(

        [embedding_a],

        [embedding_b]
    )[0][0]


    return float(similarity)


# =========================================
# DOMAIN MATCHING
# =========================================

def domain_match(

    investor_a,

    investor_b
):

    website_a = normalize_text(

        investor_a.get("website", "")
    )

    website_b = normalize_text(

        investor_b.get("website", "")
    )


    if not website_a or not website_b:

        return False


    return website_a == website_b


# =========================================
# FINAL ENTITY RESOLUTION
# =========================================

def resolve_investor_entity(

    investor_a,

    investor_b
):

    # =========================================
    # STRONG DOMAIN MATCH
    # =========================================

    if domain_match(

        investor_a,

        investor_b
    ):

        return {

            "is_same_entity": True,

            "confidence": 0.99,

            "method": "domain_match"
        }


    # =========================================
    # FUZZY NAME SCORE
    # =========================================

    fuzzy_score = fuzzy_name_similarity(

        investor_a,

        investor_b
    )


    # =========================================
    # SEMANTIC SCORE
    # =========================================

    semantic_score = semantic_similarity(

        investor_a,

        investor_b
    )


    # =========================================
    # COMBINED SCORE
    # =========================================

    combined_score = (

        (0.4 * fuzzy_score)

        +

        (0.6 * semantic_score)
    )


    # =========================================
    # ENTITY DECISION
    # =========================================

    is_same = (

        fuzzy_score >= (
            FUZZY_THRESHOLD / 100
        )

        or

        semantic_score >= (
            SEMANTIC_THRESHOLD
        )

        or

        combined_score >= 0.87
    )


    return {

        "is_same_entity": is_same,

        "confidence": round(

            combined_score,

            4
        ),

        "fuzzy_score": round(

            fuzzy_score,

            4
        ),

        "semantic_score": round(

            semantic_score,

            4
        ),

        "method": "hybrid_resolution"
    }