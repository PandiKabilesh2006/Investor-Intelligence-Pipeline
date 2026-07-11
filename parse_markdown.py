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

import re
from app.validation.investor_validation import (
    resolve_website,
    validate_parsed_investor,
    extract_domain,
)

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
# GROUP MARKDOWN FILES BY DOMAIN
# =========================================

domain_groups = {}  # domain -> list of dicts: {"md_file": file, "md_filepath": filepath, "url": url, "metadata": metadata}

for markdown_file in markdown_files:
    md_filepath = os.path.join(RAW_DATA_FOLDER, markdown_file)
    meta_filepath = md_filepath.replace(".md", ".json")
    
    metadata = {}
    if os.path.exists(meta_filepath):
        try:
            with open(meta_filepath, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load metadata for {markdown_file}: {e}")
            
    url = metadata.get("url", "")
    if not url:
        # Fallback to reconstructing URL from filename if missing
        url = markdown_file.replace("_", "/").replace(".md", "")
        if not url.startswith("http"):
            url = "https://" + url
            
    domain = extract_domain(url)
    if not domain:
        print(f"Skipping {markdown_file} because domain could not be resolved from URL: {url}")
        continue
        
    domain_groups.setdefault(domain, []).append({
        "md_file": markdown_file,
        "md_filepath": md_filepath,
        "url": url,
        "metadata": metadata
    })

print(f"Grouped {len(markdown_files)} files into {len(domain_groups)} unique domains.\n")


# =========================================
# PARSING PIPELINE
# =========================================

for domain, items in domain_groups.items():
    # Sort files in group by depth of path (homepage first)
    def get_path_depth(item):
        from urllib.parse import urlparse
        path = urlparse(item["url"]).path.strip("/")
        if not path:
            return 0
        return path.count("/") + 1
        
    sorted_items = sorted(items, key=get_path_depth)
    primary_item = sorted_items[0]
    homepage_url = primary_item["url"]
    
    # We use a safe filename based on the domain (e.g. "forumvc_com.json")
    safe_domain_filename = re.sub(r"[^a-zA-Z0-9]", "_", domain)
    json_filepath = f"{PARSED_DATA_FOLDER}/{safe_domain_filename}.json"
    
    # Check if consolidated file exists and has already processed these files
    if os.path.exists(json_filepath) and not force_reparse:
        try:
            with open(json_filepath, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            meta = existing_data.get("meta", {})
            processed_files = set(meta.get("processed_markdown_files", []))
            
            # If all files in this group are already processed, skip!
            if all(item["md_file"] in processed_files for item in items):
                print(f"Skipping domain: {domain} (all {len(items)} subpages already parsed and consolidated)")
                skipped_count += 1
                continue
        except Exception as e:
            print(f"Warning: Failed to verify existing consolidated file for {domain}: {e}")

    print("=" * 80)
    print(f"\nProcessing domain: {domain} ({len(items)} subpages)\n")
    
    # Combine markdown content of all subpages in the group
    combined_markdown = ""
    for item in sorted_items:
        try:
            with open(item["md_filepath"], "r", encoding="utf-8") as f:
                content = f.read()
            combined_markdown += f"\n\n--- SOURCE URL: {item['url']} ---\n\n" + content
        except Exception as e:
            print(f"Failed reading {item['md_file']}: {e}")
            
    try:
        # AI Structured Parsing on the combined content
        parsed_data = parse_investor(combined_markdown, source_url=homepage_url)
        
        # =====================================
        # NORMALIZATION
        # =====================================
        parsed_data["investment_stage"] = normalize_investment_stages(
            parsed_data.get("investment_stage", [])
        )
        parsed_data["focus_sectors"] = normalize_sectors(
            parsed_data.get("focus_sectors", [])
        )
        
        # =====================================
        # SOURCE URL TRACEABILITY & VALIDATION
        # =====================================
        is_valid, reason, parsed_data = validate_parsed_investor(parsed_data)
        if not is_valid:
            print(f"Rejected parsed record for domain {domain} ({reason})")
            continue
            
        firm_name = parsed_data["firm_name"]
        parsed_data["ingestion_source"] = primary_item["metadata"].get("ingestion_source", "web_crawl")
        
        # Keep raw metadata/markdown links for compatibility with insert_into_db provenance check
        parsed_data["raw_markdown_file"] = primary_item["md_file"]
        parsed_data["raw_metadata_file"] = primary_item["md_file"].replace(".md", ".json")
        parsed_data["collected_at"] = primary_item["metadata"].get("collected_at", "")
        
        parsed_data["website"] = resolve_website(
            parsed_data.get("website", ""),
            parsed_data.get("source_url", ""),
        )
        
        # Add metadata tracking for consolidated subpages
        meta = parsed_data.setdefault("meta", {})
        meta["processed_markdown_files"] = [item["md_file"] for item in items]
        meta["processed_source_urls"] = [item["url"] for item in items]
        
        # =====================================
        # SAVE PARSED JSON
        # =====================================
        with open(json_filepath, "w", encoding="utf-8") as json_file:
            json.dump(
                parsed_data,
                json_file,
                indent=4,
                ensure_ascii=False
            )
            
        parsed_count += 1
        
        # =====================================
        # TEAM PAGE DISCOVERY
        # =====================================
        try:
            team_pages_queued = discover_team_pages(
                firm=firm_name,
                website=parsed_data.get("website", "") or parsed_data.get("source_url", ""),
            )
            if team_pages_queued > 0:
                print(f"Queued {team_pages_queued} team page(s) for: {firm_name}")
        except Exception as discovery_error:
            print(f"Team page discovery failed for {firm_name}: {discovery_error}")

        # =====================================
        # PRINT STRUCTURED OUTPUT
        # =====================================
        print("Structured Consolidated Investor Data:\n")
        print(json.dumps(parsed_data, indent=4, ensure_ascii=False))
        print(f"\nSaved consolidated JSON: {json_filepath}\n")
        
    except Exception as parsing_error:
        print(f"Parsing failed for domain {domain}: {parsing_error}")
        # Store failed files in manager
        for item in items:
            add_failed_url(item["md_file"], parsing_error)

# =========================================
# FINAL SUMMARY
# =========================================
print("=" * 80)
print(
    f"\nSuccessfully parsed {parsed_count} investor domains"
    f"\nSkipped {skipped_count} domains (all files already consolidated)\n"
)
print("Parsing pipeline completed.\n")
