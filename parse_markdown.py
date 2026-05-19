import os
import json

from app.parsing.gpt_parser import parse_investor

from app.parsing.normalize import (
    normalize_investment_stages,
    normalize_sectors
)

from app.utils.deduplicate import is_duplicate_firm


# =========================================
# FOLDERS
# =========================================

RAW_DATA_FOLDER = "raw_markdown"
PARSED_DATA_FOLDER = "parsed_json"

os.makedirs(PARSED_DATA_FOLDER, exist_ok=True)


# =========================================
# GET ONLY MARKDOWN FILES
# =========================================

markdown_files = [

    file

    for file in os.listdir(RAW_DATA_FOLDER)

    if file.endswith(".md")
]

print(f"\nFound {len(markdown_files)} markdown files\n")


# =========================================
# PARSING COUNTER
# =========================================

parsed_count = 0


# =========================================
# PARSING PIPELINE
# =========================================

for markdown_file in markdown_files:

    filepath = f"{RAW_DATA_FOLDER}/{markdown_file}"

    print("=" * 80)
    print(f"\nParsing: {markdown_file}\n")

    try:

        # =========================================
        # READ MARKDOWN FILE
        # =========================================

        with open(filepath, "r", encoding="utf-8") as file:

            markdown_content = file.read()


        # =========================================
        # AI STRUCTURED PARSING
        # =========================================

        parsed_data = parse_investor(markdown_content)


        # =========================================
        # NORMALIZATION
        # =========================================

        parsed_data["investment_stage"] = (

            normalize_investment_stages(

                parsed_data.get("investment_stage", [])
            )
        )

        parsed_data["focus_sectors"] = (

            normalize_sectors(

                parsed_data.get("focus_sectors", [])
            )
        )


        # =========================================
        # VALIDATE FIRM NAME
        # =========================================

        firm_name = parsed_data.get("firm", "")
        # Handle list responses from LLM
        if isinstance(firm_name, list):
            if len(firm_name) > 0:
                firm_name = str(firm_name[0])
            else:
                firm_name = ""
        # Convert everything safely to string
        firm_name = str(firm_name).strip()
        if not firm_name:
            print("Missing firm name")
            continue
            
        # =========================================
        # INVESTOR DEDUPLICATION
        # =========================================

        if is_duplicate_firm(firm_name):

            print(f"Duplicate investor skipped: {firm_name}")

            continue


        # =========================================
        # SAVE PARSED JSON
        # =========================================

        json_filename = markdown_file.replace(".md", ".json")

        json_filepath = (

            f"{PARSED_DATA_FOLDER}/{json_filename}"
        )


        with open(json_filepath, "w", encoding="utf-8") as json_file:

            json.dump(
                parsed_data,
                json_file,
                indent=4,
                ensure_ascii=False
            )


        # =========================================
        # SUCCESS COUNTER
        # =========================================

        parsed_count += 1


        # =========================================
        # PRINT STRUCTURED OUTPUT
        # =========================================

        print("Structured Investor Data:\n")

        print(json.dumps(parsed_data, indent=4))

        print(f"\nSaved JSON: {json_filepath}\n")


    except Exception as parsing_error:

        print(f"Parsing failed: {parsing_error}")


# =========================================
# FINAL SUMMARY
# =========================================

print("=" * 80)

print(f"\nSuccessfully parsed {parsed_count} investors\n")

print("Parsing pipeline completed.\n")