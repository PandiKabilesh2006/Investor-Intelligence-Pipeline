from sentence_transformers import (
    SentenceTransformer
)


# =========================================
# EMBEDDING MODEL
# =========================================

embedding_model = SentenceTransformer(

    "all-MiniLM-L6-v2"
)


# =========================================
# BUILD INVESTOR TEXT
# =========================================

def build_investor_text(investor):

    components = [

        investor.get("firm_name", ""),

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
        ),

        " ".join(

            investor.get(
                "geography",
                []
            )
        )
    ]


    return " ".join(components)


# =========================================
# GENERATE EMBEDDING
# =========================================

def generate_investor_embedding(

    investor
):

    investor_text = build_investor_text(

        investor
    )


    embedding = embedding_model.encode(

        investor_text
    )


    return embedding.tolist()