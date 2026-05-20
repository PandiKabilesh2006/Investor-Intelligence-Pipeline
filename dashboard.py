import json
import streamlit as st

from app.database.db import SessionLocal

from app.database.models import Investor

from app.search.semantic_search import (
    semantic_investor_search
)


# =========================================
# PAGE CONFIG
# =========================================

st.set_page_config(

    page_title="Investor Intelligence Platform",

    layout="wide"
)


# =========================================
# HEADER
# =========================================

st.title(

    "Investor Intelligence Platform"
)

st.markdown(

    """
AI-powered semantic investor discovery and intelligence platform.
"""
)


# =========================================
# DATABASE SESSION
# =========================================

session = SessionLocal()


# =========================================
# SIDEBAR
# =========================================

st.sidebar.header(

    "Investor Discovery"
)


# =========================================
# SEARCH MODE
# =========================================

search_mode = st.sidebar.radio(

    "Search Mode",

    [
        "Semantic AI Search",
        "Structured Filtering"
    ]
)


# =========================================
# SEMANTIC SEARCH MODE
# =========================================

if search_mode == "Semantic AI Search":

    semantic_query = st.sidebar.text_area(

        "Describe Your Startup",

        placeholder="""
Example:
Enterprise AI workflow automation startup
raising Series A in India
"""
    )


    semantic_limit = st.sidebar.slider(

        "Maximum Results",

        min_value=5,

        max_value=100,

        value=20
    )


    semantic_search_button = (

        st.sidebar.button(

            "Run Semantic Search"
        )
    )


# =========================================
# STRUCTURED FILTERING MODE
# =========================================

else:

    sector = st.sidebar.selectbox(

        "Startup Sector",

        [
            "Artificial Intelligence",
            "B2B SaaS",
            "Voice AI",
            "Enterprise AI",
            "Fintech",
            "Healthcare",
            "Developer Tools",
            "AI Infrastructure"
        ]
    )


    stage = st.sidebar.selectbox(

        "Investment Stage",

        [
            "Pre-Seed",
            "Seed",
            "Series A",
            "Series B",
            "Series C",
            "Growth Stage",
            "IPO Stage"
        ]
    )


    geography = st.sidebar.selectbox(

        "Geography",

        [
            "United States",
            "India",
            "Europe",
            "Southeast Asia"
        ]
    )


    minimum_score = st.sidebar.slider(

        "Minimum Match Score",

        min_value=1,

        max_value=13,

        value=5
    )


    structured_search_button = (

        st.sidebar.button(

            "Find Investors"
        )
    )


# =========================================
# LOAD ALL INVESTORS
# =========================================

all_investors = (

    session.query(Investor).all()
)


# =========================================
# ANALYTICS
# =========================================

st.subheader(

    "Platform Analytics"
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(

        "Total Investors",

        len(all_investors)
    )


with col2:

    st.metric(

        "Search Engine",

        "Semantic AI"
    )


with col3:

    st.metric(

        "Database",

        "PostgreSQL + pgvector"
    )


st.markdown("---")


# =========================================
# SEMANTIC SEARCH EXECUTION
# =========================================

if (

    search_mode == "Semantic AI Search"

    and

    semantic_search_button
):

    if not semantic_query.strip():

        st.warning(

            "Please enter a search query."
        )

    else:

        with st.spinner(

            "Running semantic investor retrieval..."
        ):

            results = semantic_investor_search(

                query=semantic_query,

                limit=semantic_limit
            )


        st.subheader(

            "Semantic Investor Matches"
        )


        st.write(

            f"Found {len(results)} semantic matches"
        )


        if len(results) == 0:

            st.warning(

                "No semantic matches found."
            )


        else:

            for investor in results:

                st.markdown("---")


                st.subheader(

                    investor["firm_name"]
                )


                st.write(

                    f"Website: "
                    f"{investor['website']}"
                )


                try:

                    sectors = json.loads(

                        investor[
                            "focus_sectors"
                        ]
                        or
                        "[]"
                    )

                except:

                    sectors = []


                try:

                    stages = json.loads(

                        investor[
                            "investment_stage"
                        ]
                        or
                        "[]"
                    )

                except:

                    stages = []


                try:

                    geographies = json.loads(

                        investor[
                            "geography"
                        ]
                        or
                        "[]"
                    )

                except:

                    geographies = []


                similarity_score = round(

                    1 - investor["distance"],

                    4
                )


                st.write(

                    f"Semantic Similarity: "
                    f"{similarity_score}"
                )


                st.write(

                    f"Sectors: "
                    f"{', '.join(sectors)}"
                )


                st.write(

                    f"Stages: "
                    f"{', '.join(stages)}"
                )


                st.write(

                    f"Geography: "
                    f"{', '.join(geographies)}"
                )


# =========================================
# STRUCTURED FILTERING EXECUTION
# =========================================

if (

    search_mode == "Structured Filtering"

    and

    structured_search_button
):

    ranked_investors = []


    # =========================================
    # INVESTOR RANKING
    # =========================================

    for investor in all_investors:

        score = 0


        try:

            sectors = json.loads(

                investor.focus_sectors
                or
                "[]"
            )

        except:

            sectors = []


        try:

            stages = json.loads(

                investor.investment_stage
                or
                "[]"
            )

        except:

            stages = []


        try:

            geographies = json.loads(

                investor.geography
                or
                "[]"
            )

        except:

            geographies = []


        # =========================================
        # SECTOR MATCH
        # =========================================

        if any(

            sector.lower()
            in
            s.lower()

            for s in sectors
        ):

            score += 5


        # =========================================
        # STAGE MATCH
        # =========================================

        if any(

            stage.lower()
            in
            s.lower()

            for s in stages
        ):

            score += 5


        # =========================================
        # GEOGRAPHY MATCH
        # =========================================

        if any(

            geography.lower()
            in
            g.lower()

            for g in geographies
        ):

            score += 3


        # =========================================
        # SCORE FILTER
        # =========================================

        if score >= minimum_score:

            ranked_investors.append(

                {

                    "firm_name":

                    investor.firm_name,

                    "website":

                    investor.website,

                    "score":

                    score,

                    "sectors":

                    ", ".join(sectors),

                    "stages":

                    ", ".join(stages),

                    "geography":

                    ", ".join(geographies)
                }
            )


    # =========================================
    # SORT RESULTS
    # =========================================

    ranked_investors = sorted(

        ranked_investors,

        key=lambda x: x["score"],

        reverse=True
    )


    st.subheader(

        "Structured Investor Matches"
    )


    st.write(

        f"Found "
        f"{len(ranked_investors)} "
        f"matching investors"
    )


    if len(ranked_investors) == 0:

        st.warning(

            "No matching investors found."
        )


    else:

        for investor in ranked_investors:

            st.markdown("---")


            st.subheader(

                investor["firm_name"]
            )


            st.write(

                f"Website: "
                f"{investor['website']}"
            )


            st.write(

                f"Match Score: "
                f"{investor['score']}"
            )


            st.write(

                f"Sectors: "
                f"{investor['sectors']}"
            )


            st.write(

                f"Stages: "
                f"{investor['stages']}"
            )


            st.write(

                f"Geography: "
                f"{investor['geography']}"
            )


# =========================================
# FOOTER
# =========================================

st.markdown("---")

st.caption(

    "AI-Native Investor Intelligence Platform"
)


# =========================================
# CLOSE DATABASE SESSION
# =========================================

session.close()