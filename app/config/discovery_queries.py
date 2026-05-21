from app.config.ingestion_universe import (
    generate_ingestion_queries
)


# =========================================
# DYNAMIC DISCOVERY QUERIES
# =========================================

DISCOVERY_QUERIES = (

    generate_ingestion_queries()
)