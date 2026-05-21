import json
import streamlit as st
import pandas as pd

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

    page_icon="🚀",

    layout="wide",

    initial_sidebar_state="expanded"
)


# =========================================
# CUSTOM CSS
# =========================================

st.markdown(
    """
    <style>

    .main {
        background-color: #0E1117;
    }

    .block-container {
        padding-top: 2rem;
    }

    .investor-card {
        background-color: #161B22;
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid #30363D;
        margin-bottom: 1.2rem;
    }

    .metric-card {
        background-color: #161B22;
        padding: 1rem;
        border-radius: 14px;
        border: 1px solid #30363D;
        text-align: center;
    }

    .tag {
        display: inline-block;
        background-color: #21262D;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
        font-size: 0.85rem;
    }

    .score-box {
        background-color: #238636;
        padding: 0.4rem 0.8rem;
        border-radius: 10px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    </style>
    """,

    unsafe_allow_html=True
)


# =========================================
# DATABASE SESSION
# =========================================

session = SessionLocal()


# =========================================
# LOAD INVESTORS
# =========================================

all_investors = session.query(Investor).all()


# =========================================
# HEADER
# =========================================

st.title("🚀 Investor Intelligence Platform")

st.markdown(
    """
AI-native semantic investor discovery platform powered by:
- PostgreSQL + pgvector
- Semantic embeddings
- Hybrid retrieval
- Structured investor intelligence
"""
)


# =========================================
# TOP METRICS
# =========================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.markdown(
        f"""
        <div class="metric-card">
            <h2>{len(all_investors)}</h2>
            <p>Total Investors</p>
        </div>
        """,

        unsafe_allow_html=True
    )

with col2:

    st.markdown(
        """
        <div class="metric-card">
            <h2>Semantic AI</h2>
            <p>Search Engine</p>
        </div>
        """,

        unsafe_allow_html=True
    )

with col3:

    st.markdown(
        """
        <div class="metric-card">
            <h2>pgvector</h2>
            <p>Vector Database</p>
        </div>
        """,

        unsafe_allow_html=True
    )

with col4:

    st.markdown(
        """
        <div class="metric-card">
            <h2>Hybrid</h2>
            <p>Retrieval Mode</p>
        </div>
        """,

        unsafe_allow_html=True
    )


st.markdown("---")


# =========================================
# SIDEBAR
# =========================================

st.sidebar.title("🔎 Investor Discovery")


search_mode = st.sidebar.radio(

    "Search Mode",

    [

        "Semantic Search",

        "Structured Search"
    ]
)


# =========================================
# SEMANTIC SEARCH INPUTS
# =========================================

if search_mode == "Semantic Search":

    query = st.sidebar.text_area(

        "Describe Your Startup",

        placeholder="""
Example:

Enterprise AI workflow automation startup
raising Series A in India
"""
    )


    sector = st.sidebar.selectbox(

        "Sector Filter",

        [

            "",

            "Artificial Intelligence",

            "Enterprise AI",

            "B2B SaaS",

            "Voice AI"
        ]
    )


    stage = st.sidebar.selectbox(

        "Investment Stage",

        [

            "",

            "Pre-Seed",

            "Seed",

            "Series A",

            "Series B",

            "Growth Stage"
        ]
    )


    geography = st.sidebar.selectbox(

        "Geography",

        [

            "",

            "India",

            "United States",

            "Europe",

            "Southeast Asia",

            "Middle East",

            "Global"
        ]
    )


    limit = st.sidebar.slider(

        "Maximum Results",

        5,

        100,

        20
    )


    run_search = st.sidebar.button(

        "Run Semantic Search"
    )


# =========================================
# STRUCTURED SEARCH INPUTS
# =========================================

else:

    sector_filter = st.sidebar.selectbox(

        "Sector",

        [

            "Artificial Intelligence",

            "Enterprise AI",

            "B2B SaaS",

            "Voice AI"
        ]
    )


    stage_filter = st.sidebar.selectbox(

        "Stage",

        [

            "Pre-Seed",

            "Seed",

            "Series A",

            "Series B",

            "Growth Stage"
        ]
    )


    geography_filter = st.sidebar.selectbox(

        "Geography",

        [

            "India",

            "United States",

            "Europe",

            "Southeast Asia",

            "Middle East",

            "Global"
        ]
    )


    run_structured = st.sidebar.button(

        "Find Investors"
    )


# =========================================
# TABS
# =========================================

tab1, tab2 = st.tabs(

    [

        "Investor Discovery",

        "Database Analytics"
    ]
)


# =========================================
# INVESTOR DISCOVERY TAB
# =========================================

with tab1:

    # =====================================
    # SEMANTIC SEARCH
    # =====================================

    if (

        search_mode == "Semantic Search"

        and

        run_search
    ):

        if not query.strip():

            st.warning(

                "Please enter a search query."
            )

        else:

            with st.spinner(

                "Running semantic investor retrieval..."
            ):

                results = semantic_investor_search(

                    query=query,

                    sector=sector if sector else None,

                    stage=stage if stage else None,

                    geography=geography if geography else None,

                    limit=limit
                )


            st.subheader(

                "🎯 Semantic Investor Matches"
            )


            st.write(

                f"Found {len(results)} investors"
            )


            if not results:

                st.warning(

                    "No matching investors found."
                )


            for investor in results:

                similarity_score = round(

                    (1 - investor["distance"]) * 100,

                    2
                )


                sectors = investor.get(

                    "focus_sectors",

                    []
                ) or []


                stages = investor.get(

                    "investment_stage",

                    []
                ) or []


                geographies = investor.get(

                    "geography",

                    []
                ) or []


                contact_links = investor.get(

                    "contact_links",

                    []
                ) or []


                partners = investor.get(

                    "partners",

                    []
                ) or []


                portfolio_companies = investor.get(

                    "portfolio_companies",

                    []
                ) or []


                st.markdown(

                    f"""
                    <div class="investor-card">

                    <h2>{investor['firm_name']}</h2>

                    <p>
                    🌐 <a href="{investor['website']}" target="_blank">
                    {investor['website']}
                    </a>
                    </p>

                    <div class="score-box">
                    {similarity_score}% Match
                    </div>

                    </div>
                    """,

                    unsafe_allow_html=True
                )


                st.progress(

                    min(similarity_score / 100, 1.0)
                )


                # =============================
                # SECTORS
                # =============================

                st.markdown(

                    '<div class="section-title">Sectors</div>',

                    unsafe_allow_html=True
                )


                for sector_item in sectors:

                    st.markdown(

                        f"""
                        <span class="tag">
                        {sector_item}
                        </span>
                        """,

                        unsafe_allow_html=True
                    )


                # =============================
                # STAGES
                # =============================

                st.markdown(

                    '<div class="section-title">Investment Stages</div>',

                    unsafe_allow_html=True
                )


                for stage_item in stages:

                    st.markdown(

                        f"""
                        <span class="tag">
                        {stage_item}
                        </span>
                        """,

                        unsafe_allow_html=True
                    )


                # =============================
                # GEOGRAPHY
                # =============================

                st.markdown(

                    '<div class="section-title">Geography</div>',

                    unsafe_allow_html=True
                )


                for geo in geographies:

                    st.markdown(

                        f"""
                        <span class="tag">
                        {geo}
                        </span>
                        """,

                        unsafe_allow_html=True
                    )


                # =============================
                # PARTNERS
                # =============================

                if partners:

                    st.markdown(

                        '<div class="section-title">Partners</div>',

                        unsafe_allow_html=True
                    )


                    st.write(

                        ", ".join(partners)
                    )


                # =============================
                # PORTFOLIO COMPANIES
                # =============================

                if portfolio_companies:

                    st.markdown(

                        '<div class="section-title">Portfolio Companies</div>',

                        unsafe_allow_html=True
                    )


                    st.write(

                        ", ".join(
                            portfolio_companies
                        )
                    )


                # =============================
                # CONTACT LINKS
                # =============================

                if contact_links:

                    st.markdown(

                        '<div class="section-title">Contact Links</div>',

                        unsafe_allow_html=True
                    )


                    for link in contact_links:

                        st.markdown(

                            f"- [{link}]({link})"
                        )


                st.markdown("---")


    # =====================================
    # STRUCTURED SEARCH
    # =====================================

    if (

        search_mode == "Structured Search"

        and

        run_structured
    ):

        filtered_results = []


        for investor in all_investors:

            sectors = investor.focus_sectors or []

            stages = investor.investment_stage or []

            geographies = investor.geography or []


            if (

                sector_filter in sectors

                and

                stage_filter in stages

                and

                geography_filter in geographies
            ):

                filtered_results.append(

                    investor
                )


        st.subheader(

            "📊 Structured Investor Matches"
        )


        st.write(

            f"Found {len(filtered_results)} investors"
        )


        for investor in filtered_results:

            st.markdown(

                f"""
                <div class="investor-card">

                <h2>{investor.firm}</h2>

                <p>
                🌐 <a href="{investor.website}" target="_blank">
                {investor.website}
                </a>
                </p>

                </div>
                """,

                unsafe_allow_html=True
            )


            st.write(

                f"**Sectors:** "
                f"{', '.join(investor.focus_sectors or [])}"
            )


            st.write(

                f"**Stages:** "
                f"{', '.join(investor.investment_stage or [])}"
            )


            st.write(

                f"**Geography:** "
                f"{', '.join(investor.geography or [])}"
            )


            st.markdown("---")


# =========================================
# ANALYTICS TAB
# =========================================

with tab2:

    st.subheader(

        "📈 Platform Analytics"
    )


    investor_data = []


    for investor in all_investors:

        investor_data.append({

            "Firm":

            investor.firm,

            "Website":

            investor.website,

            "Sectors":

            ", ".join(
                investor.focus_sectors or []
            ),

            "Stages":

            ", ".join(
                investor.investment_stage or []
            ),

            "Geography":

            ", ".join(
                investor.geography or []
            )
        })


    df = pd.DataFrame(

        investor_data
    )


    st.dataframe(

        df,

        use_container_width=True
    )


# =========================================
# FOOTER
# =========================================

st.markdown("---")

st.caption(

    "AI-Native Investor Intelligence Platform • PostgreSQL + pgvector + Semantic Retrieval"
)


# =========================================
# CLOSE SESSION
# =========================================

session.close()