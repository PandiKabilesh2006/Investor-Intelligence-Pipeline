import os
import json

from app.database.db import SessionLocal

from app.database.models import (
    Investor,
    Partner,
    PortfolioCompany
)

from app.entity.entity_resolver import (
    resolve_investor_entity
)

from app.entity.entity_merger import (
    merge_investor_entities
)

from app.embeddings.embedder import (
    generate_investor_embedding
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

merged_count = 0


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
# BUILD EXISTING INVESTOR RECORD
# =========================================

def build_existing_investor_record(

    db_investor
):

    return {

        "firm": db_investor.firm_name,

        "website": db_investor.website,

        "focus_sectors": json.loads(

            db_investor.focus_sectors or "[]"
        ),

        "investment_stage": json.loads(

            db_investor.investment_stage or "[]"
        ),

        "geography": json.loads(

            db_investor.geography or "[]"
        )
    }


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

            incoming_data = json.load(file)


        # =========================================
        # VALIDATE FIRM NAME
        # =========================================

        firm_name = normalize_field(

            incoming_data.get("firm")
        ).strip()


        if not firm_name:

            print("Missing firm name")

            continue


        # =========================================
        # FIND CANONICAL MATCH
        # =========================================

        existing_investors = (

            session.query(Investor).all()
        )


        canonical_match = None


        for existing_db_investor in existing_investors:

            existing_data = (

                build_existing_investor_record(

                    existing_db_investor
                )
            )


            resolution = (

                resolve_investor_entity(

                    existing_data,

                    incoming_data
                )
            )


            if resolution["is_same_entity"]:

                canonical_match = (

                    existing_db_investor
                )

                print(

                    f"Matched existing investor: "
                    f"{existing_db_investor.firm_name}"
                )

                print(

                    f"Confidence: "
                    f"{resolution['confidence']}"
                )

                break


        # =========================================
        # MERGE EXISTING ENTITY
        # =========================================

        if canonical_match:

            canonical_data = {

                "firm": canonical_match.firm_name,

                "website": canonical_match.website,

                "focus_sectors": json.loads(

                    canonical_match.focus_sectors or "[]"
                ),

                "investment_stage": json.loads(

                    canonical_match.investment_stage or "[]"
                ),

                "partners": [

                    partner.name

                    for partner in (
                        canonical_match.partners
                    )
                ],

                "portfolio_companies": [

                    company.company_name

                    for company in (
                        canonical_match
                        .portfolio_companies
                    )
                ],

                "geography": json.loads(

                    canonical_match.geography or "[]"
                ),

                "contact_links": []
            }


            merged_entity = (

                merge_investor_entities(

                    canonical_data,

                    incoming_data
                )
            )


            # =========================================
            # GENERATE UPDATED EMBEDDING
            # =========================================

            merged_embedding = (

                generate_investor_embedding(

                    merged_entity
                )
            )


            # =========================================
            # UPDATE CANONICAL ENTITY
            # =========================================

            canonical_match.website = (

                merged_entity["website"]
            )


            canonical_match.focus_sectors = (

                json.dumps(

                    merged_entity[
                        "focus_sectors"
                    ]
                )
            )


            canonical_match.investment_stage = (

                json.dumps(

                    merged_entity[
                        "investment_stage"
                    ]
                )
            )


            canonical_match.geography = (

                json.dumps(

                    merged_entity[
                        "geography"
                    ]
                )
            )


            canonical_match.embedding = (

                merged_embedding
            )


            # =========================================
            # UPDATE PARTNERS
            # =========================================

            existing_partner_names = set(

                partner.name.lower()

                for partner in (
                    canonical_match.partners
                )
            )


            for partner_name in (

                merged_entity["partners"]
            ):

                normalized_partner = (

                    partner_name.lower()
                )


                if normalized_partner in (

                    existing_partner_names
                ):

                    continue


                new_partner = Partner(

                    investor_id=canonical_match.id,

                    name=partner_name
                )

                session.add(new_partner)


            # =========================================
            # UPDATE PORTFOLIO COMPANIES
            # =========================================

            existing_company_names = set(

                company.company_name.lower()

                for company in (
                    canonical_match
                    .portfolio_companies
                )
            )


            for company_name in (

                merged_entity[
                    "portfolio_companies"
                ]
            ):

                normalized_company = (

                    company_name.lower()
                )


                if normalized_company in (

                    existing_company_names
                ):

                    continue


                new_company = PortfolioCompany(

                    investor_id=canonical_match.id,

                    company_name=company_name
                )

                session.add(new_company)


            session.commit()

            merged_count += 1


            print(

                f"Merged investor entity: "
                f"{canonical_match.firm_name}"
            )

            continue


        # =========================================
        # GENERATE INVESTOR EMBEDDING
        # =========================================

        embedding = (

            generate_investor_embedding(

                incoming_data
            )
        )


        # =========================================
        # CREATE NEW INVESTOR ENTITY
        # =========================================

        investor = Investor(

            firm_name=firm_name,

            website=normalize_field(

                incoming_data.get("website")
            ),

            focus_sectors=json.dumps(

                incoming_data.get(
                    "focus_sectors",
                    []
                )
            ),

            investment_stage=json.dumps(

                incoming_data.get(
                    "investment_stage",
                    []
                )
            ),

            geography=json.dumps(

                incoming_data.get(
                    "geography",
                    []
                )
            ),

            embedding=embedding
        )


        session.add(investor)

        session.commit()

        session.refresh(investor)


        # =========================================
        # INSERT PARTNERS
        # =========================================

        partners = incoming_data.get(

            "partners",
            []
        )


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

        companies = incoming_data.get(

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


        session.commit()

        inserted_count += 1


        print(

            f"Inserted new investor: "
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

    f"\nInserted investors: "
    f"{inserted_count}"
)

print(

    f"Merged investors: "
    f"{merged_count}\n"
)