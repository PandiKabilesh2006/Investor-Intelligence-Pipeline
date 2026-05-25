import os
import json

from app.parsing.gpt_parser import parse_investor

from app.parsing.normalize import (
    normalize_investment_stages,
    normalize_sectors
)

from app.utils.deduplicate import (
    is_duplicate_firm
)

from app.utils.failed_url_manager import add_failed_url

from app.utils.groq_circuit import reset_groq_70b_circuit

reset_groq_70b_circuit()

# =========================================
# FOLDERS
# =========================================

RAW_DATA_FOLDER = "raw_markdown"

PARSED_DATA_FOLDER = "parsed_json"

os.makedirs(

    PARSED_DATA_FOLDER,

    exist_ok=True
)


# =========================================
# GET ONLY MARKDOWN FILES
# =========================================

markdown_files = [

    file

    for file in os.listdir(RAW_DATA_FOLDER)

    if file.endswith(".md")
]


print(

    f"\nFound {len(markdown_files)} markdown files\n"
)


# =========================================
# PARSING COUNTER
# =========================================

parsed_count = 0


# =========================================
# PARSING PIPELINE
# =========================================

for markdown_file in markdown_files:

    filepath = (

        f"{RAW_DATA_FOLDER}/{markdown_file}"
    )


    print("=" * 80)

    print(

        f"\nParsing: {markdown_file}\n"
    )


    try:

        # =====================================
        # READ MARKDOWN FILE
        # =====================================

        with open(

            filepath,

            "r",

            encoding="utf-8"
        ) as file:

            markdown_content = file.read()


        # =====================================
        # LOAD METADATA
        # =====================================

        metadata_filepath = (

            filepath.replace(

                ".md",

                ".json"
            )
        )


        metadata = {}


        if os.path.exists(metadata_filepath):

            try:

                with open(

                    metadata_filepath,

                    "r",

                    encoding="utf-8"
                ) as metadata_file:

                    metadata = json.load(

                        metadata_file
                    )

            except Exception as metadata_error:

                print(

                    f"Metadata load failed: "
                    f"{metadata_error}"
                )


        # =====================================
        # AI STRUCTURED PARSING
        # =====================================

        parsed_data = parse_investor(

            markdown_content
        )


        # =====================================
        # NORMALIZATION
        # =====================================

        parsed_data["investment_stage"] = (

            normalize_investment_stages(

                parsed_data.get(

                    "investment_stage",

                    []
                )
            )
        )


        parsed_data["focus_sectors"] = (

            normalize_sectors(

                parsed_data.get(

                    "focus_sectors",

                    []
                )
            )
        )


        # =====================================
        # SOURCE URL TRACEABILITY
        # =====================================

        parsed_data["source_url"] = metadata.get(

            "url",

            ""
        )


        # =====================================
        # VALIDATE FIRM NAME
        # =====================================

        firm_name = parsed_data.get(

            "firm",

            ""
        )


        # =====================================
        # HANDLE LIST RESPONSES
        # =====================================

        if isinstance(firm_name, list):

            if len(firm_name) > 0:

                firm_name = str(

                    firm_name[0]
                )

            else:

                firm_name = ""


        # =====================================
        # SAFE STRING CLEANUP
        # =====================================

        firm_name = str(

            firm_name
        ).strip()


        # =====================================
        # MISSING FIRM NAME
        # =====================================

        if not firm_name:

            print(

                "Missing firm name"
            )

            continue


        parsed_data["firm"] = firm_name


        # =====================================
        # INVESTOR DEDUPLICATION
        # =====================================

        if is_duplicate_firm(

            firm_name
        ):

            print(

                f"Duplicate investor skipped: "
                f"{firm_name}"
            )

            continue


        # =====================================
        # SAVE PARSED JSON
        # =====================================

        json_filename = markdown_file.replace(

            ".md",

            ".json"
        )


        json_filepath = (

            f"{PARSED_DATA_FOLDER}/"
            f"{json_filename}"
        )


        with open(

            json_filepath,

            "w",

            encoding="utf-8"
        ) as json_file:

            json.dump(

                parsed_data,

                json_file,

                indent=4,

                ensure_ascii=False
            )


        # =====================================
        # SUCCESS COUNTER
        # =====================================

        parsed_count += 1


        # =====================================
        # PRINT STRUCTURED OUTPUT
        # =====================================

        print(

            "Structured Investor Data:\n"
        )


        print(

            json.dumps(

                parsed_data,

                indent=4,

                ensure_ascii=False
            )
        )


        print(

            f"\nSaved JSON: "
            f"{json_filepath}\n"
        )


    except Exception as parsing_error:

        print(

            f"Parsing failed: "
            f"{parsing_error}"
        )
        # =====================================
        # STORE FAILED FILE
        # =====================================
        add_failed_url(
            markdown_file,
            parsing_error
    )

# =========================================
# FINAL SUMMARY
# =========================================

print("=" * 80)

print(

    f"\nSuccessfully parsed "
    f"{parsed_count} investors\n"
)

print(

    "Parsing pipeline completed.\n"
)