"""
Remove investors with invalid firm names or rejected domains from the database.

Usage:
  python cleanup_bad_investors.py          # dry run (report only)
  python cleanup_bad_investors.py --apply  # delete bad records
"""

import argparse
import sys

import psycopg2

from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from app.validation.investor_validation import (
    extract_domain,
    is_rejected_firm_name,
    is_rejected_url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean invalid investor records from DB")
    parser.add_argument("--apply", action="store_true", help="Actually delete records")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, firm_name, website FROM investors ORDER BY id")
    rows = cursor.fetchall()

    to_delete = []
    for investor_id, firm_name, website in rows:
        reasons = []
        if is_rejected_firm_name(firm_name or ""):
            reasons.append("rejected_firm_name")
        if website and is_rejected_url(website):
            reasons.append("rejected_website")
        domain = extract_domain(website or "")
        if domain and is_rejected_url(f"https://{domain}"):
            reasons.append("rejected_domain")

        if reasons:
            to_delete.append((investor_id, firm_name, website, reasons))

    print(f"Scanned {len(rows)} investors; {len(to_delete)} marked for removal.\n")

    for investor_id, firm_name, website, reasons in to_delete:
        print(f"  [{investor_id}] {firm_name!r} | {website!r} -> {', '.join(reasons)}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to delete.")
        conn.close()
        return 0

    if not to_delete:
        print("\nNothing to delete.")
        conn.close()
        return 0

    for investor_id, _, _, _ in to_delete:
        cursor.execute("DELETE FROM partners WHERE investor_id = %s", (investor_id,))
        cursor.execute("DELETE FROM portfolio_companies WHERE investor_id = %s", (investor_id,))
        cursor.execute("DELETE FROM investors WHERE id = %s", (investor_id,))

    conn.commit()
    conn.close()
    print(f"\nDeleted {len(to_delete)} invalid investor record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
