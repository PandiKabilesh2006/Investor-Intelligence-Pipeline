from typing import List, Dict, Any
from urllib.parse import urlparse

def _get_domain(url: str) -> str:
    """Extract the core domain (e.g., a16z.com) from a website URL."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        # remove www.
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except:
        return ""

def _clean_name(name: str) -> tuple[str, str]:
    """Split a name into first and last, removing titles/punctuation."""
    clean = ''.join(c for c in name.lower() if c.isalpha() or c.isspace())
    parts = clean.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]

def generate_guessed_emails(investors: List[Dict[str, Any]]):
    """
    Enriches the investor list in-place by adding a 'guessed_emails' field
    for each partner based on standard VC email patterns.
    """
    for inv in investors:
        domain = _get_domain(inv.get("website", ""))
        if not domain:
            inv["guessed_emails"] = []
            continue

        partners = inv.get("partners", [])
        if not isinstance(partners, list):
            inv["guessed_emails"] = []
            continue

        all_guesses = []
        for partner in partners:
            if not isinstance(partner, dict):
                continue
            name = partner.get("name", "")
            if not name:
                continue
            
            first, last = _clean_name(name)
            if not first:
                continue
            
            guesses = []
            if last:
                guesses.append(f"{first}@{domain}")           # marc@a16z.com
                guesses.append(f"{first}.{last}@{domain}")    # marc.andreessen@a16z.com
                guesses.append(f"{first[0]}{last}@{domain}")  # mandreessen@a16z.com
            else:
                guesses.append(f"{first}@{domain}")
                
            partner_guesses = ", ".join(guesses)
            all_guesses.append(f"{name}: [{partner_guesses}]")
            
        inv["guessed_emails"] = all_guesses
