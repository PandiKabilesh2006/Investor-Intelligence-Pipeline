import json
from pathlib import Path

from sqlalchemy import text

from app.database.db import engine
from app.utils.contact_link_extractor import extract_contact_links_from_markdown
from app.utils.normalization import merge_clean_lists


RAW_MARKDOWN_DIR = Path("raw_markdown")
PARSED_JSON_DIR = Path("parsed_json")


def repair_contact_links(dry_run=True):
    updates = []

    for parsed_path in PARSED_JSON_DIR.glob("*.json"):
        raw_path = RAW_MARKDOWN_DIR / parsed_path.name.replace(".json", ".md")

        if not raw_path.exists():
            continue

        try:
            parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
            markdown = raw_path.read_text(encoding="utf-8")
        except Exception:
            continue

        firm = str(parsed.get("firm") or "").strip()

        if not firm:
            continue

        existing_links = parsed.get("contact_links") or []
        extracted_links = extract_contact_links_from_markdown(
            markdown,
            firm=firm,
            website=parsed.get("website", ""),
            source_url=parsed.get("source_url", ""),
        )
        merged_links = merge_clean_lists(existing_links, extracted_links)

        if len(merged_links) <= len(existing_links):
            continue

        updates.append(
            {
                "firm": firm,
                "contact_links": merged_links,
                "added": [
                    link
                    for link in merged_links
                    if link not in existing_links
                ],
            }
        )

    if not dry_run and updates:
        with engine.begin() as conn:
            for update in updates:
                conn.execute(
                    text(
                        """
                        UPDATE investors
                        SET contact_links = :contact_links,
                            updated_at = NOW()
                        WHERE lower(firm) = lower(:firm)
                        """
                    ),
                    {
                        "firm": update["firm"],
                        "contact_links": update["contact_links"],
                    },
                )

    print(f"Records with new contact links: {len(updates)}")

    for update in updates[:50]:
        print(f"- {update['firm']}: +{len(update['added'])}")
        for link in update["added"][:5]:
            print(f"  {link}")

    if dry_run:
        print("\nDry run only. Apply with: python repair_contact_links_from_markdown.py --apply")
    else:
        print("\nApplied contact link updates.")


if __name__ == "__main__":
    import sys

    repair_contact_links(dry_run="--apply" not in sys.argv)
