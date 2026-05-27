import os
import json
import sys

from app.parsing.gpt_parser import parse_investor

from app.parsing.normalize import (
    normalize_investment_stages,
    normalize_sectors
)
from app.config.settings import (
    PARSED_DATA_FOLDER,
    RAW_DATA_FOLDER,
)

from app.utils.deduplicate import (
    is_duplicate_firm,
    reset_firm_dedup_cache,
)
from app.validation.investor_validation import (
    resolve_website,
    validate_parsed_investor,
)

reset_firm_dedup_cache()

from app.utils.failed_url_manager import add_failed_url

from app.utils.team_page_discovery import discover_team_pages

# =========================================
# FOLDERS
# =========================================

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

skipped_count = 0

force_reparse = "--force" in sys.argv


# =========================================
# PARSING PIPELINE
# =========================================

for markdown_file in markdown_files:

    json_filename = markdown_file.replace(".md", ".json")

    json_filepath = f"{PARSED_DATA_FOLDER}/{json_filename}"

    if os.path.exists(json_filepath) and not force_reparse:

        print(f"Skipping: {markdown_file} (already parsed JSON exists)")

        skipped_count += 1

        continue


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

        source_url = metadata.get("url", "")

        if not source_url:
            print(f"Rejected markdown without source URL metadata: {markdown_file}")
            continue

        parsed_data = parse_investor(markdown_content, source_url=source_url)


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

        is_valid, reason, parsed_data = validate_parsed_investor(parsed_data)

        if not is_valid:
            print(f"Rejected parsed record ({reason}): {markdown_file}")
            continue

        firm_name = parsed_data["firm_name"]
        parsed_data["ingestion_source"] = metadata.get("ingestion_source", "web_crawl")
        parsed_data["raw_markdown_file"] = markdown_file
        parsed_data["raw_metadata_file"] = os.path.basename(metadata_filepath)
        parsed_data["collected_at"] = metadata.get("collected_at", "")
        parsed_data["website"] = resolve_website(
            parsed_data.get("website", ""),
            parsed_data.get("source_url", ""),
        )

        if is_duplicate_firm(firm_name):
            print(f"Duplicate investor skipped: {firm_name}")
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
        # TEAM PAGE DISCOVERY
        # After parsing any source (blog, article,
        # directory), queue the firm's team pages
        # so real partner names can be scraped.
        # =====================================

        try:

            team_pages_queued = discover_team_pages(
                firm=firm_name,
                website=parsed_data.get("website", "") or parsed_data.get("source_url", ""),
            )

            if team_pages_queued > 0:

                print(

                    f"Queued {team_pages_queued} team page(s) "
                    f"for: {firm_name}"
                )

        except Exception as discovery_error:

            print(

                f"Team page discovery failed for {firm_name}: "
                f"{discovery_error}"
            )


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

    f"\nSuccessfully parsed {parsed_count} investors"

    f"\nSkipped {skipped_count} already parsed files\n"
)

print(

    "Parsing pipeline completed.\n"
)
