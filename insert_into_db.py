import os
import json

from app.database.db import SessionLocal

from app.database.models import (
    Investor,
    Partner,
    PortfolioCompany
)


# =========================================
# CONFIG
# =========================================

PARSED_JSON_FOLDER = "parsed_json"


# =========================================
# DATABASE SESSION
# =========================================

session = SessionLocal()


# =========================================
# LOAD JSON FILES
# =========================================

json_files = [

    file

    for file in os.listdir(PARSED_JSON_FOLDER)

    if file.endswith(".json")
]


print(f"\nFound {len(json_files)} parsed JSON files\n")


# =========================================
# COUNTERS
# =========================================

inserted_count = 0


# =========================================
# BLOCKED LOW-QUALITY SOURCES
# =========================================

blocked_keywords = [

    "media",
    "quora",
    "reddit",
    "news",
    "blog",
    "article"
]


# =========================================
# FIELD NORMALIZATION
# =========================================

def normalize_field(value):

    if isinstance(value, list):

        if len(value) == 1:

            return str(value[0])

        return ", ".join(

            [str(v) for v in value]
        )

    if value is None:

        return ""

    return str(value)


# =========================================
# MAIN INSERTION LOOP
# =========================================

for json_file in json_files:

    filepath = f"{PARSED_JSON_FOLDER}/{json_file}"

    print("=" * 80)
    print(f"\nProcessing: {json_file}\n")

    try:

        # =========================================
        # LOAD PARSED JSON
        # =========================================

        with open(filepath, "r", encoding="utf-8") as file:

            data = json.load(file)


        # =========================================
        # NORMALIZE FIRM NAME
        # =========================================

        firm_name = normalize_field(

            data.get("firm")
        ).strip()


        # =========================================
        # VALIDATE FIRM NAME
        # =========================================

        if not firm_name:

            print("Missing firm name")

            continue


        # =========================================
        # FILTER LOW-QUALITY RESULTS
        # =========================================

        firm_name_lower = firm_name.lower()


        if any(

            keyword in firm_name_lower

            for keyword in blocked_keywords
        ):

            print(

                f"Skipping low-quality investor: "
                f"{firm_name}"
            )

            continue


        # =========================================
        # CHECK DUPLICATE INVESTOR
        # =========================================

        existing_investor = (

            session.query(Investor)

            .filter(

                Investor.firm_name == firm_name
            )

            .first()
        )


        if existing_investor:

            print(

                f"Investor already exists: "
                f"{firm_name}"
            )

            continue


        # =========================================
        # CREATE INVESTOR RECORD
        # =========================================

        investor = Investor(

            firm_name=firm_name,

            website=normalize_field(

                data.get("website")
            ),

            focus_sectors=json.dumps(

                data.get(
                    "focus_sectors",
                    []
                )
            ),

            investment_stage=json.dumps(

                data.get(
                    "investment_stage",
                    []
                )
            ),

            geography=json.dumps(

                data.get(
                    "geography",
                    []
                )
            )
        )


        session.add(investor)

        session.commit()

        session.refresh(investor)


        # =========================================
        # INSERT PARTNERS
        # =========================================

        partners = data.get("partners", [])


        if isinstance(partners, str):

            partners = [partners]


        for partner_name in partners:

            partner_name = normalize_field(

                partner_name
            ).strip()


            if not partner_name:

                continue


            partner = Partner(

                investor_id=investor.id,

                name=partner_name
            )

            session.add(partner)


        # =========================================
        # INSERT PORTFOLIO COMPANIES
        # =========================================

        companies = data.get(

            "portfolio_companies",
            []
        )


        if isinstance(companies, str):

            companies = [companies]


        for company_name in companies:

            company_name = normalize_field(

                company_name
            ).strip()


            if not company_name:

                continue


            company = PortfolioCompany(

                investor_id=investor.id,

                company_name=company_name
            )

            session.add(company)


        # =========================================
        # FINAL COMMIT
        # =========================================

        session.commit()


        inserted_count += 1


        print(

            f"Inserted investor: "
            f"{firm_name}"
        )


    except Exception as insert_error:

        session.rollback()

        print(

            f"Insertion failed: "
            f"{insert_error}"
        )


# =========================================
# CLOSE SESSION
# =========================================

session.close()


# =========================================
# FINAL SUMMARY
# =========================================

print("=" * 80)

print(

    f"\nSuccessfully inserted "
    f"{inserted_count} investors\n"
)