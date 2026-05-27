"""
reparse_for_partners.py
=======================
Re-parses ALL raw markdown files with OpenAI GPT-4o.
Groups pages by firm name, merges partners from ALL sub-pages
(team, people, partners, leadership, etc.) into a single enriched
record, then upserts into the database.

Run: venv\Scripts\python.exe -u reparse_for_partners.py
"""

import os
import json
import sys
from collections import defaultdict

from app.parsing.gpt_parser import parse_investor
from app.parsing.normalize import normalize_investment_stages, normalize_sectors
from app.validation.investor_validation import resolve_website, validate_parsed_investor
from app.config.settings import RAW_DATA_FOLDER, PARSED_DATA_FOLDER
from insert_into_db import insert_investor_data

os.makedirs(PARSED_DATA_FOLDER, exist_ok=True)

RAW = RAW_DATA_FOLDER
PARSED = PARSED_DATA_FOLDER


# =========================================
# STEP 1: Parse every markdown file
# =========================================

print("\n" + "=" * 70)
print("STEP 1: Parsing all raw markdown files with OpenAI GPT-4o")
print("=" * 70 + "\n")

# Map: firm_name (lower) -> best merged record
firm_records = {}   # firm_name_lower -> merged dict
firm_aliases = {}   # firm_name_lower -> canonical firm_name string

markdown_files = sorted([f for f in os.listdir(RAW) if f.endswith(".md")])
print(f"Found {len(markdown_files)} markdown files\n")

for i, md_file in enumerate(markdown_files, 1):
    md_path = os.path.join(RAW, md_file)
    meta_path = md_path.replace(".md", ".json")

    # Load source URL from metadata
    source_url = ""
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8", errors="replace") as f:
                meta = json.load(f)
            source_url = meta.get("url", "")
        except Exception:
            pass

    if not source_url:
        print(f"[{i}/{len(markdown_files)}] SKIP (no source URL): {md_file}")
        continue

    try:
        with open(md_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        print(f"[{i}/{len(markdown_files)}] READ ERROR: {md_file} — {e}")
        continue

    print(f"[{i}/{len(markdown_files)}] Parsing: {md_file}")

    try:
        parsed = parse_investor(content, source_url=source_url)
    except Exception as e:
        print(f"  Parse failed: {e}")
        continue

    firm_name = parsed.get("firm_name", "").strip()
    if not firm_name:
        print(f"  Skipped: no firm_name extracted")
        continue

    firm_key = firm_name.lower()

    if firm_key not in firm_records:
        # First time seeing this firm — initialize record
        parsed["focus_sectors"] = normalize_sectors(parsed.get("focus_sectors", []))
        parsed["investment_stage"] = normalize_investment_stages(parsed.get("investment_stage", []))
        firm_records[firm_key] = parsed
        firm_aliases[firm_key] = firm_name
        print(f"  NEW firm: {firm_name} — {len(parsed.get('partners', []))} partners")
    else:
        # Merge into existing record — partners especially
        existing = firm_records[firm_key]

        # Merge partners (dedup by name)
        existing_partner_names = {
            p.get("name", "").strip().lower()
            for p in existing.get("partners", [])
            if isinstance(p, dict)
        }
        new_partners = [
            p for p in parsed.get("partners", [])
            if isinstance(p, dict)
            and p.get("name", "").strip().lower() not in existing_partner_names
            and p.get("name", "").strip()
        ]
        if new_partners:
            existing.setdefault("partners", []).extend(new_partners)
            existing_partner_names.update(
                p.get("name", "").strip().lower() for p in new_partners
            )
            print(f"  MERGE into {firm_name}: +{len(new_partners)} new partners (total {len(existing['partners'])})")
        else:
            print(f"  MERGE into {firm_name}: no new partners")

        # Merge portfolio companies (dedup by company_name)
        existing_pc_names = {
            (c.get("company_name", "") if isinstance(c, dict) else str(c)).lower()
            for c in existing.get("portfolio_companies", [])
        }
        new_pcs = [
            c for c in parsed.get("portfolio_companies", [])
            if (c.get("company_name", "") if isinstance(c, dict) else str(c)).lower()
            not in existing_pc_names
        ]
        if new_pcs:
            existing.setdefault("portfolio_companies", []).extend(new_pcs)

        # Merge focus_sectors, investment_stage, geography
        for field in ["focus_sectors", "investment_stage", "geography"]:
            existing_vals = set(existing.get(field, []))
            for v in parsed.get(field, []):
                if v and v not in existing_vals:
                    existing.setdefault(field, []).append(v)
                    existing_vals.add(v)

        # Use best website
        if not existing.get("website") and parsed.get("website"):
            existing["website"] = parsed["website"]

        firm_records[firm_key] = existing


# =========================================
# STEP 2: Validate & save enriched JSONs
# =========================================

print("\n" + "=" * 70)
print("STEP 2: Validating and saving enriched JSONs")
print("=" * 70 + "\n")

valid_firms = {}
for firm_key, record in firm_records.items():
    is_valid, reason, record = validate_parsed_investor(record)
    if not is_valid:
        print(f"  REJECTED ({reason}): {record.get('firm_name', firm_key)}")
        continue

    record["website"] = resolve_website(
        record.get("website", ""),
        record.get("source_url", ""),
    )

    # Save to parsed_json using firm name as filename
    safe_name = "".join(
        c if c.isalnum() or c in "-_ " else "_"
        for c in record["firm_name"]
    ).strip().replace(" ", "_")[:80]
    json_path = os.path.join(PARSED, f"enriched_{safe_name}.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=4, ensure_ascii=False)

    valid_firms[firm_key] = record
    partners = record.get("partners", [])
    partner_with_role = sum(1 for p in partners if isinstance(p, dict) and p.get("role"))
    print(f"  Saved: {record['firm_name']} — {len(partners)} partners ({partner_with_role} with role)")


# =========================================
# STEP 3: Upsert into database
# =========================================

print("\n" + "=" * 70)
print(f"STEP 3: Upserting {len(valid_firms)} firms into PostgreSQL")
print("=" * 70 + "\n")

success = 0
failed = 0

for firm_key, record in valid_firms.items():
    try:
        insert_investor_data(record)
        success += 1
        print(f"  UPSERTED: {record['firm_name']}")
    except Exception as e:
        failed += 1
        print(f"  FAILED:   {record['firm_name']} — {e}")


# =========================================
# SUMMARY
# =========================================

print("\n" + "=" * 70)
print("DONE")
print(f"  Firms processed: {len(firm_records)}")
print(f"  Firms upserted:  {success}")
print(f"  Firms failed:    {failed}")

# Quick DB check
try:
    from app.database.db import SessionLocal
    from app.database.models import Partner
    s = SessionLocal()
    total_p = s.query(Partner).count()
    with_role = s.query(Partner).filter(Partner.role != None, Partner.role != "").count()
    with_li = s.query(Partner).filter(Partner.linkedin_url != None, Partner.linkedin_url != "").count()
    s.close()
    print(f"\n  DB Partners total:    {total_p}")
    print(f"  DB Partners with role:{with_role} ({100*with_role//max(total_p,1)}%)")
    print(f"  DB Partners with LinkedIn:{with_li} ({100*with_li//max(total_p,1)}%)")
except Exception as e:
    print(f"  DB check failed: {e}")

print("=" * 70 + "\n")
