import json
import streamlit as st

from app.database.db import SessionLocal
from app.database.models import Investor


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

st.title("Investor Intelligence Platform")

st.markdown(

    """
AI-powered investor discovery, ranking, and intelligence platform.
"""
)


# =========================================
# SIDEBAR INPUTS
# =========================================

st.sidebar.header("Startup Requirements")


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


search_button = st.sidebar.button(

    "Find Investors"
)


# =========================================
# DATABASE SEARCH
# =========================================

if search_button:

    session = SessionLocal()

    investors = session.query(Investor).all()

    ranked_investors = []


    # =========================================
    # RANK INVESTORS
    # =========================================

    for investor in investors:

        score = 0


        sectors = json.loads(

            investor.focus_sectors or "[]"
        )

        stages = json.loads(

            investor.investment_stage or "[]"
        )

        geographies = json.loads(

            investor.geography or "[]"
        )


        # =========================================
        # EXACT SECTOR MATCH
        # =========================================

        sector_match = False


        for investor_sector in sectors:

            if (

                sector.strip().lower()

                ==

                investor_sector.strip().lower()
            ):

                sector_match = True

                break


        if sector_match:

            score += 5


        # =========================================
        # EXACT STAGE MATCH
        # =========================================

        stage_match = False


        for investor_stage in stages:

            if (

                stage.strip().lower()

                ==

                investor_stage.strip().lower()
            ):

                stage_match = True

                break


        if stage_match:

            score += 5


        # =========================================
        # GEOGRAPHY MATCH
        # =========================================

        geography_match = False


        for investor_geography in geographies:

            if (

                geography.strip().lower()

                in

                investor_geography.strip().lower()
            ):

                geography_match = True

                break


        if geography_match:

            score += 3


        # =========================================
        # STRICT FILTERING
        # =========================================

        if (

            geography_match

            and

            score >= minimum_score
        ):

            ranked_investors.append(

                {
                    "Investor Firm": investor.firm_name,

                    "Website": investor.website,

                    "Match Score": score,

                    "Focus Sectors": ", ".join(sectors),

                    "Investment Stages": ", ".join(stages),

                    "Geography": ", ".join(geographies)
                }
            )


    # =========================================
    # SORT RESULTS
    # =========================================

    ranked_investors = sorted(

        ranked_investors,

        key=lambda x: x["Match Score"],

        reverse=True
    )


    # =========================================
    # ANALYTICS
    # =========================================

    st.subheader("Investor Match Analytics")


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(

            "Total Investors",

            len(ranked_investors)
        )


    with col2:

        top_score = (

            ranked_investors[0]["Match Score"]

            if ranked_investors

            else 0
        )

        st.metric(

            "Highest Match Score",

            top_score
        )


    with col3:

        st.metric(

            "Selected Stage",

            stage
        )


    # =========================================
    # RESULTS
    # =========================================

    st.subheader("Top Matching Investors")


    if len(ranked_investors) == 0:

        st.warning(

            "No matching investors found."
        )


    else:

        st.dataframe(

            ranked_investors,

            use_container_width=True
        )


    session.close()


# =========================================
# FOOTER
# =========================================

st.markdown("---")

st.caption(

    "Investor Intelligence Pipeline"
)