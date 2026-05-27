import csv
from typing import List, Dict, Any

def export_to_csv(investors: List[Dict[str, Any]], filepath: str):
    """
    Export the parsed investor data to a CSV file for easy importing into Excel/Airtable.
    Lists and dictionaries are collapsed into readable strings.
    """
    if not investors:
        return

    # Extract all possible keys from the schema (using the first investor as a template)
    # We define a fixed order for the most important fields
    headers = [
        "firm", "website", "confidence_score",
        "fund_size", "fund_number", "active_status", "pitch_process",
        "check_size", "thesis",
        "investment_stage", "focus_sectors", "domain_specializations", "geography",
        "partners", "portfolio_companies", "contact_links", "guessed_emails"
    ]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()

        for inv in investors:
            row = {}
            for key in headers:
                val = inv.get(key, "")
                
                # Format lists nicely
                if isinstance(val, list):
                    if not val:
                        row[key] = ""
                    elif isinstance(val[0], dict):
                        # Handle complex lists like contact_links [{"type": "email", "value": "x@x.com"}]
                        items = []
                        for item in val:
                            if "name" in item and "role" in item:
                                items.append(f"{item.get('name')} ({item.get('role')})")
                            elif "type" in item and "value" in item:
                                items.append(f"{item.get('type')}: {item.get('value')}")
                            elif "name" in item:
                                items.append(item.get("name"))
                            else:
                                items.append(str(item))
                        row[key] = " | ".join(items)
                    else:
                        # Simple lists like strings
                        row[key] = ", ".join(str(v) for v in val)
                else:
                    row[key] = str(val)
            
            writer.writerow(row)
