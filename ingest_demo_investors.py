from app.extraction.firecrawl_extract import extract_website
from app.parsing.gpt_parser import parse_investor
from app.parsing.normalize import normalize_investment_stages, normalize_sectors
from app.validation.investor_validation import validate_parsed_investor
from insert_into_db import insert_investor_data


DEMO_INVESTOR_URLS = [
    "https://a16z.com",
    "https://www.gv.com",
    "https://www.bessemer.com",
    "https://www.accel.com",
    "https://www.greylock.com",
    "https://www.lightspeedvp.com",
    "https://www.benchmark.com",
    "https://www.firstround.com",
]


def ingest_url(url):
    print("=" * 80)
    print(f"Processing: {url}")

    markdown = extract_website(url)

    if not markdown:
        print(f"Skipped: no markdown extracted for {url}")
        return False

    parsed = parse_investor(markdown, source_url=url)
    parsed["focus_sectors"] = normalize_sectors(parsed.get("focus_sectors", []))
    parsed["investment_stage"] = normalize_investment_stages(
        parsed.get("investment_stage", [])
    )

    is_valid, reason, parsed = validate_parsed_investor(parsed)

    if not is_valid:
        print(f"Rejected: {url} | {reason}")
        return False

    insert_investor_data(parsed)
    print(f"Inserted/updated: {parsed.get('firm_name')}")
    return True


def main():
    success_count = 0

    for url in DEMO_INVESTOR_URLS:
        try:
            if ingest_url(url):
                success_count += 1
        except Exception as error:
            print(f"Failed: {url} | {error}")

    print("=" * 80)
    print(f"Demo investor ingestion complete: {success_count}/{len(DEMO_INVESTOR_URLS)}")


if __name__ == "__main__":
    main()
