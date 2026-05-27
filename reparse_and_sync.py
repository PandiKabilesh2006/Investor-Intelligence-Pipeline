import os
import sys
import json
import time

# Reconfigure console encoding
sys.stdout.reconfigure(encoding='utf-8')

from app.parsing.gpt_parser import parse_investor
from app.validation.investor_validation import validate_parsed_investor
from insert_into_db import main as sync_db

RAW_FOLDER = "raw_markdown"
PARSED_FOLDER = "parsed_json"

os.makedirs(PARSED_FOLDER, exist_ok=True)

markdown_files = [f for f in os.listdir(RAW_FOLDER) if f.endswith(".md")]
total_files = len(markdown_files)

print("=" * 80)
print(f"Starting re-parsing of {total_files} real markdown files...")
print("=" * 80)

success_count = 0

for index, md_file in enumerate(markdown_files, start=1):
    md_path = os.path.join(RAW_FOLDER, md_file)
    json_filename = md_file.replace(".md", ".json")
    json_path = os.path.join(PARSED_FOLDER, json_filename)
    metadata_path = md_path.replace(".md", ".json")

    print(f"\n[{index}/{total_files}] Processing: {md_file}")

    # Load metadata (source URL)
    metadata = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"  Warning: failed to load metadata: {e}")

    try:
        # Read markdown
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        source_url = metadata.get("url", "")
        parsed = parse_investor(content, source_url=source_url)

        is_valid, reason, parsed = validate_parsed_investor(parsed)
        if not is_valid:
            print(f"  Skipping ({reason})")
            continue

        firm = parsed.get("firm_name", "")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=4, ensure_ascii=False)

        print(f"  Success! Parsed firm: '{firm}' | Partners: {len(parsed.get('partners', []))}")
        success_count += 1

    except Exception as err:
        print(f"  Error parsing file: {err}")

print("\n" + "=" * 80)
print(f"Re-parsing completed! Successfully parsed {success_count}/{total_files} files.")
print("Starting PostgreSQL database synchronization...")
print("=" * 80)

try:
    sync_db()
    print("PostgreSQL database successfully synchronized with updated partners!")
except Exception as sync_err:
    print(f"Error during database sync: {sync_err}")
